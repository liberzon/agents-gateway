"""
Email Toolkit

This module provides the EmailToolkit class for multi-provider
email management with support for Gmail and Microsoft Outlook Mail.

Usage:
    >>> from toolkits.email import EmailToolkit
    >>> toolkit = EmailToolkit(
    ...     user_id="user123",
    ...     service_name="gmail",
    ...     auth=True
    ... )
    >>> # Use with Agno agent
    >>> from agno.agent import Agent
    >>> agent = Agent(tools=[toolkit])
"""

import logging
from typing import Any, Dict, List, Optional

from agno.tools import Toolkit

from toolkits.base import BaseToolkit
from workspace_suite import EmailService
from workspace_suite.config import ProviderConfig
from workspace_suite.models import EmailMessage, EmailResult
from workspace_suite.providers.google_gmail import GoogleGmailProvider
from workspace_suite.providers.microsoft_mail import MicrosoftMailProvider
from workspace_suite.transformers.gmail_link_transformer import transform_gmail_to_link_data

logger = logging.getLogger(__name__)


# ---------------------------
# Exceptions
# ---------------------------
class EmailAuthError(RuntimeError):
    """Exception raised when email authentication fails."""

    pass


# ---------------------------
# Email Toolkit
# ---------------------------
class EmailToolkit(BaseToolkit):
    """
    AI Agent toolkit for email management operations with multi-provider support.

    This toolkit provides intelligent email management capabilities for AI agents,
    supporting both Gmail and Microsoft Outlook Mail. It handles OAuth
    authentication, token management, email operations, and provides graceful
    fallbacks when authentication is unavailable.

    ARCHITECTURE
    ============
    The toolkit follows a confirmation-based workflow where the AI agent proposes
    email operations, the user reviews and confirms, and then the operation is executed.
    This prevents unwanted email sending and allows users to edit details
    before committing.

    Token Management:
    -----------------
    - Uses a shared TokenCache (toolkits.token_cache) for efficient token storage across instances
    - Supports multiple email providers (Gmail, Outlook) via service_name parameter
    - Tokens are cached with TTL-based expiration (default: 5 minutes)
    - Automatic token refresh and error handling with cooldown periods

    Authentication Flow:
    -------------------
    1. If user has valid token → toolkit provides email management tools
    2. If no valid token → toolkit provides auth_required tool
    3. User authenticates via OAuth flow when prompted
    4. Subsequent requests automatically use authenticated service

    SUPPORTED SERVICES
    ==================
    - Gmail (service_name="gmail")
    - Microsoft Outlook Mail (service_name="outlook_mail")

    TOOLS PROVIDED
    ==============
    When authenticated (auth=True):
    - send_email: Send email immediately (requires confirmation)
    - create_draft: Create draft email (requires confirmation)
    - send_draft: Send existing draft (requires confirmation)
    - trash_email: Move email to trash (requires confirmation)
    - delete_email_permanently: Permanently delete email (requires confirmation)
    - modify_labels: Add/remove labels (requires confirmation)
    - search_emails: Search mailbox with email details and Gmail links (no confirmation)
    - list_drafts: List draft emails (no confirmation)
    - error_card: Display error messages with retry options

    When not authenticated (auth=False):
    - auth_required: Prompt user to authenticate email service

    CONFIRMATION WORKFLOW
    =====================
    Write operations (send/draft/delete/modify) require confirmation:
    1. Agent calls operation with proposed details
    2. Run pauses and returns tool call details to client
    3. Client displays interactive form for user to review/edit
    4. User confirms, skips, or cancels
    5. Client sends confirmed tools via /chat/commit endpoint
    6. Agent resumes and executes the actual email API call
    7. Operation is executed and confirmation is returned

    USAGE EXAMPLES
    ==============
    Basic initialization:
        >>> toolkit = EmailToolkit(
        ...     user_id="user123",
        ...     service_name="gmail",
        ...     auth=True
        ... )

    Multi-provider setup:
        >>> gmail_toolkit = EmailToolkit(
        ...     user_id="user123",
        ...     service_name="gmail"
        ... )
        >>> outlook_toolkit = EmailToolkit(
        ...     user_id="user123",
        ...     service_name="outlook_mail"
        ... )

    No-auth fallback:
        >>> no_auth_toolkit = EmailToolkit(
        ...     user_id="user123",
        ...     service_name="email",
        ...     auth=False
        ... )

    CLASS ATTRIBUTES
    ================
    http_timeout_s : float
        HTTP request timeout in seconds (default: 15.0)

    INSTANCE ATTRIBUTES
    ===================
    user_id : str
        User identifier for token lookup and attribution

    service_name : str
        Email service identifier ("gmail", "outlook_mail", etc.)

    context : Dict[str, Any]
        Runtime context including token_valid status

    METHODS
    =======
    Public Tools:
    - send_email(): Send email immediately (requires confirmation)
    - create_draft(): Create draft email (requires confirmation)
    - send_draft(): Send existing draft (requires confirmation)
    - trash_email(): Move email to trash (requires confirmation)
    - delete_email_permanently(): Permanently delete (requires confirmation)
    - modify_labels(): Add/remove labels (requires confirmation)
    - search_emails(): Search mailbox with email details (no confirmation)
    - read_email(): Read full email content - requires specific ID (no confirmation)
    - list_drafts(): List drafts (no confirmation)
    - auth_required(): Prompt for email authentication
    - error_card(): Display error messages

    Internal Helpers:
    - _prepare_auth(): Manage OAuth token retrieval and validation

    ERROR HANDLING
    ==============
    - EmailAuthError: Token fetch failures, expired tokens
    - HTTP errors: API quota limits, permission issues, network failures
    - Validation errors: Invalid email addresses, missing required fields

    All errors are caught and returned as structured error cards with retry options.

    SECURITY
    ========
    - Tokens never exposed in logs or responses
    - OAuth scopes limited to mail.send/read (no full account access)
    - User confirmation required before any email sending or deletion
    - Service account authentication for backend token storage

    INTEGRATION
    ===========
    This toolkit is designed to work with:
    - Agno 2.0 Agent framework
    - FastAPI backend with /chat and /chat/commit endpoints
    - Rich-formatted CLI client for interactive confirmations
    - Backend token service for OAuth token management

    SEE ALSO
    ========
    - TokenCache: Shared token caching system (toolkits.token_cache)
    - fetch_access_token(): Module-level token fetcher (must be provided by application)
    """

    http_timeout_s = 15.0

    def __init__(
        self,
        user_id: str,
        service_name: str,
        auth: bool = True,
        fetch_token_func=None,
    ):
        """
        Initialize the EmailToolkit.

        Args:
            user_id: User identifier for token lookup (tools_user_id)
            service_name: Email service name ("gmail", "outlook_mail", etc.)
            auth: Whether user is authenticated (determines which tools are available)
            fetch_token_func: Optional function to fetch access tokens. If not provided,
                            toolkit will attempt to import from parent module.
        """
        # Call BaseToolkit.__init__ which will call _initialize_service()
        BaseToolkit.__init__(self, user_id, service_name, auth, fetch_token_func)

        # Build tools list AFTER service is initialized (methods need self.email_service)
        tools_list: list = []
        confirmation_tools_list = []

        if auth:
            tools_list.append(self.send_email)
            tools_list.append(self.create_draft)
            tools_list.append(self.send_draft)
            tools_list.append(self.trash_email)
            tools_list.append(self.delete_email_permanently)
            tools_list.append(self.modify_labels)
            tools_list.append(self.search_emails)
            # tools_list.append(self.read_email)  # Commented out - use search_emails with gmail_link instead
            tools_list.append(self.list_drafts)
            confirmation_tools_list = [
                "send_email",
                "create_draft",
                "send_draft",
                "trash_email",
                "delete_email_permanently",
                "modify_labels",
            ]
        else:
            tools_list.append(self.email_auth_required)

        # Call Toolkit base class __init__ LAST with complete tools list
        Toolkit.__init__(
            self,
            name="EmailToolkit",
            tools=tools_list,
            requires_confirmation_tools=confirmation_tools_list,
            show_result_tools=[],
            stop_after_tool_call_tools=([] if auth else ["email_auth_required"]),
        )

    def _initialize_service(self) -> None:
        """Initialize email service with appropriate provider."""
        config = ProviderConfig()

        if "gmail" in self.service_name.lower() or "google" in self.service_name.lower():
            provider: GoogleGmailProvider | MicrosoftMailProvider = GoogleGmailProvider(config)
        elif "outlook" in self.service_name.lower() or "microsoft" in self.service_name.lower():
            provider = MicrosoftMailProvider(config)  # type: ignore[assignment]
        else:
            # Default to Gmail
            provider = GoogleGmailProvider(config)

        self.email_service = EmailService(provider)

    # ---------------------------
    # Tools
    # ---------------------------

    def send_email(
        self,
        to: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email immediately.

        This tool sends an email to specified recipients. It requires
        confirmation before execution.

        Args:
            to: List of recipient email addresses (required)
            subject: Email subject line (required)
            body_text: Plain text body content (optional)
            body_html: HTML body content (optional)
            cc: List of CC recipient addresses (optional)
            bcc: List of BCC recipient addresses (optional)
            attachments: List of file paths to attach (optional)
            thread_id: Thread ID for replying to existing thread (optional)

        Returns:
            Dictionary with status and email details:
            {
                "status": "success" | "error",
                "id": "message_id_123",
                "thread_id": "thread_id_456",
                "to": ["recipient@example.com"],
                "subject": "Meeting Tomorrow",
                "error": {...} (if status=error)
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # Create email message
            msg = EmailMessage(
                to=tuple(to),
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                cc=tuple(cc) if cc else (),
                bcc=tuple(bcc) if bcc else (),
                attachments=tuple(attachments) if attachments else (),
                thread_id=thread_id,
            )

            # Call email service
            result: EmailResult = self.email_service.send(token=token, msg=msg)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "id": result.id,
                    "thread_id": result.thread_id,
                    "to": to,
                    "subject": subject,
                }
            else:
                return {
                    "status": "error",
                    "error": result.error or {"message": "Failed to send email"},
                }

        except EmailAuthError as e:
            logger.error(f"Auth error in send_email: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in send_email: {e}")
            return self.error_card(f"Failed to send email: {e}")

    def create_draft(
        self,
        to: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a draft email.

        This tool creates a draft email without sending. Requires confirmation before execution.

        Args:
            to: List of recipient email addresses
            subject: Email subject line
            body_text: Plain text body content (optional)
            body_html: HTML body content (optional)
            cc: List of CC recipient addresses (optional)
            bcc: List of BCC recipient addresses (optional)

        Returns:
            Dictionary with status and draft details
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # Create email message
            msg = EmailMessage(
                to=tuple(to),
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                cc=tuple(cc) if cc else (),
                bcc=tuple(bcc) if bcc else (),
            )

            # Call email service
            result: EmailResult = self.email_service.draft(token=token, msg=msg)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "id": result.id,
                    "thread_id": result.thread_id,
                    "to": to,
                    "subject": subject,
                    "type": "draft",
                }
            else:
                return {
                    "status": "error",
                    "error": result.error or {"message": "Failed to create draft"},
                }

        except EmailAuthError as e:
            logger.error(f"Auth error in create_draft: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in create_draft: {e}")
            return self.error_card(f"Failed to create draft: {e}")

    def send_draft(
        self,
        draft_id: str,
    ) -> Dict[str, Any]:
        """
        Send an existing draft email.

        This tool sends a previously created draft. Requires confirmation before execution.

        Args:
            draft_id: ID of the draft to send

        Returns:
            Dictionary with status and sent email details
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # Call email service
            result: EmailResult = self.email_service.send_draft(token=token, draft_id=draft_id)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "id": result.id,
                    "draft_id": draft_id,
                }
            else:
                return {
                    "status": "error",
                    "draft_id": draft_id,
                    "error": result.error or {"message": "Failed to send draft"},
                }

        except EmailAuthError as e:
            logger.error(f"Auth error in send_draft: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in send_draft: {e}")
            return self.error_card(f"Failed to send draft: {e}")

    def trash_email(
        self,
        message_id: str,
    ) -> Dict[str, Any]:
        """
        Move an email to trash.

        This tool moves an email to the trash folder. Requires confirmation before execution.

        Args:
            message_id: ID of the email to trash

        Returns:
            Dictionary with status, operation confirmation, and email details:
            {
                "status": "success" | "error",
                "id": "msg123",
                "operation": "trashed",
                "subject": "Meeting Tomorrow",
                "from": "alice@example.com",
                "from_name": "Alice Smith",
                "date": "2025-10-28T10:30:00-07:00",
                "snippet": "Hi, let's meet tomorrow at 2pm"
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # First, fetch email details before trashing
            email_details: Dict[str, Any] = {}
            is_gmail = "gmail" in self.service_name.lower() or "google" in self.service_name.lower()

            try:
                email_data = self.email_service.read(token=token, message_id=message_id)

                if is_gmail:
                    link_data = transform_gmail_to_link_data(email_data)
                    email_details = {
                        "subject": link_data.subject,
                        "from": link_data.from_address,
                        "from_name": link_data.from_name,
                        "date": link_data.date.isoformat(),
                        "snippet": link_data.snippet,
                    }
                else:
                    email_details = {
                        "subject": email_data.get("subject", ""),
                        "from": email_data.get("from", ""),
                        "date": email_data.get("date", ""),
                        "snippet": email_data.get("snippet", ""),
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch email details before trashing {message_id}: {e}")

            # Call email service to trash
            result: EmailResult = self.email_service.trash(token=token, message_id=message_id)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "id": message_id,
                    "operation": "trashed",
                    "message": "Email moved to trash successfully",
                    **email_details,  # Include email details if available
                }
            else:
                return {
                    "status": "error",
                    "id": message_id,
                    "error": result.error or {"message": "Failed to trash email"},
                }

        except EmailAuthError as e:
            logger.error(f"Auth error in trash_email: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in trash_email: {e}")
            return self.error_card(f"Failed to trash email: {e}")

    def delete_email_permanently(
        self,
        message_id: str,
    ) -> Dict[str, Any]:
        """
        Delete an email permanently.

        This tool permanently deletes an email (cannot be undone).
        Requires confirmation before execution.

        Args:
            message_id: ID of the email to delete permanently

        Returns:
            Dictionary with status, deletion confirmation, and email details:
            {
                "status": "success" | "error",
                "id": "msg123",
                "operation": "deleted_permanently",
                "subject": "Meeting Tomorrow",
                "from": "alice@example.com",
                "from_name": "Alice Smith",
                "date": "2025-10-28T10:30:00-07:00",
                "snippet": "Hi, let's meet tomorrow at 2pm"
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # First, fetch email details before deleting
            email_details: Dict[str, Any] = {}
            is_gmail = "gmail" in self.service_name.lower() or "google" in self.service_name.lower()

            try:
                email_data = self.email_service.read(token=token, message_id=message_id)

                if is_gmail:
                    link_data = transform_gmail_to_link_data(email_data)
                    email_details = {
                        "subject": link_data.subject,
                        "from": link_data.from_address,
                        "from_name": link_data.from_name,
                        "date": link_data.date.isoformat(),
                        "snippet": link_data.snippet,
                    }
                else:
                    email_details = {
                        "subject": email_data.get("subject", ""),
                        "from": email_data.get("from", ""),
                        "date": email_data.get("date", ""),
                        "snippet": email_data.get("snippet", ""),
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch email details before permanent deletion {message_id}: {e}")

            # Call email service to permanently delete
            result: EmailResult = self.email_service.delete_permanently(token=token, message_id=message_id)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "id": message_id,
                    "operation": "deleted_permanently",
                    "message": "Email permanently deleted",
                    **email_details,  # Include email details if available
                }
            else:
                return {
                    "status": "error",
                    "id": message_id,
                    "error": result.error or {"message": "Failed to delete email"},
                }

        except EmailAuthError as e:
            logger.error(f"Auth error in delete_email_permanently: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in delete_email_permanently: {e}")
            return self.error_card(f"Failed to delete email: {e}")

    def modify_labels(
        self,
        id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Add or remove labels from an email.

        This tool modifies labels/categories on an email. Requires confirmation before execution.

        Args:
            id: message or thread ID of the email to modify
            add_labels: List of label names to add (optional)
            remove_labels: List of label names to remove (optional)

        Returns:
            Dictionary with status and modified labels
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # Call email service
            result: EmailResult = self.email_service.modify_labels(
                token=token, message_id=id, add_labels=add_labels, remove_labels=remove_labels
            )

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "id": id,
                    "add_labels": add_labels or [],
                    "remove_labels": remove_labels or [],
                }
            else:
                return {
                    "status": "error",
                    "id": id,
                    "error": result.error or {"message": "Failed to modify labels"},
                }

        except EmailAuthError as e:
            logger.error(f"Auth error in modify_labels: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in modify_labels: {e}")
            return self.error_card(f"Failed to modify labels: {e}")

    def search_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Search emails by query and return email details with links.

        This tool searches the mailbox using provider-specific query syntax
        and returns email properties. For Gmail, includes web links and attachment info.
        No confirmation required.

        Args:
            query: Search query (e.g., "from:john@example.com subject:meeting").
                   If not provided, defaults to listing inbox emails ("in:inbox").
            max_results: Maximum number of results to return (default: 10)

        Returns:
            Dictionary with status and email details:
            {
                "status": "success" | "error",
                "query": "from:john",
                "emails": [
                    {
                        "id": "msg_id_1",
                        "subject": "Meeting Tomorrow",
                        "from": "john@example.com",
                        "from_name": "John Doe",  # Gmail only
                        "date": "2025-10-26T10:30:00Z",
                        "snippet": "Let's discuss the project...",
                        "labels": ["INBOX", "UNREAD"],
                        "is_unread": true,  # Gmail only
                        "gmail_link": "https://mail.google.com/mail/u/0/#inbox/msg_id_1",  # Gmail only
                        "attachments": [{"filename": "doc.pdf", "mime_type": "application/pdf"}],  # Gmail only
                        "thread_id": "thread_123"  # Gmail only
                    },
                    ...
                ],
                "total_count": 42
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # Default to inbox if no query provided
            actual_query = query if query else "in:inbox"

            # Search for message IDs
            message_ids: list[str] = self.email_service.search(token=token, query=actual_query, max_results=max_results)

            # Fetch details for each email
            emails = []
            is_gmail = "gmail" in self.service_name.lower() or "google" in self.service_name.lower()

            for msg_id in message_ids:
                try:
                    email_data = self.email_service.read(token=token, message_id=msg_id)

                    # Use transformer for Gmail to get link data
                    if is_gmail:
                        link_data = transform_gmail_to_link_data(email_data)
                        emails.append(
                            {
                                "id": link_data.message_id,
                                "subject": link_data.subject,
                                "from": link_data.from_address,
                                "from_name": link_data.from_name,
                                "date": link_data.date.isoformat(),
                                "snippet": link_data.snippet,
                                "labels": link_data.labels,
                                "is_unread": link_data.is_unread,
                                "gmail_link": link_data.gmail_link,
                                "attachments": [
                                    {"filename": att.filename, "mime_type": att.mime_type}
                                    for att in link_data.attachments
                                ],
                                "thread_id": link_data.thread_id,
                            }
                        )
                    else:
                        # Fallback for non-Gmail providers (Microsoft, etc.)
                        emails.append(
                            {
                                "id": msg_id,
                                "subject": email_data.get("subject", ""),
                                "from": email_data.get("from", ""),
                                "date": email_data.get("date", ""),
                                "snippet": email_data.get("snippet", ""),
                                "labels": email_data.get("labels", []),
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to read email {msg_id}: {e}")
                    # Include partial data with error indicator
                    emails.append({"id": msg_id, "error": str(e)})

            return {
                "status": "success",
                "query": actual_query,
                "emails": emails,
                "total_count": len(emails),
            }

        except EmailAuthError as e:
            logger.error(f"Auth error in search_emails: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in search_emails: {e}")
            return self.error_card(f"Failed to search emails: {e}")

    # def read_email(
    #     self,
    #     message_id: str,
    # ) -> Dict[str, Any]:
    #     """
    #     Read an email's full content.
    #
    #     This tool retrieves the complete content of a specific email.
    #     Requires a valid message_id - will not be invoked without one.
    #     No confirmation required.
    #
    #     IMPORTANT: This tool should only be called when the user explicitly
    #     requests to read a specific email or when a specific email ID is
    #     already known from search results. Do not call this tool speculatively
    #     or without a valid message_id.
    #
    #     Args:
    #         message_id: ID of the email to read (required, must not be empty)
    #
    #     Returns:
    #         Dictionary with status and email content:
    #         {
    #             "status": "success" | "error",
    #             "id": "msg_id_123",
    #             "subject": "Meeting Tomorrow",
    #             "from": "sender@example.com",
    #             "to": ["recipient@example.com"],
    #             "date": "2025-10-26T10:30:00Z",
    #             "body_text": "Full email content...",
    #             "body_html": "<html>...",
    #             "labels": ["INBOX"],
    #             "thread_id": "thread_456"
    #         }
    #     """
    #     try:
    #         # Validate message_id is provided and not empty
    #         if not message_id or not message_id.strip():
    #             return {
    #                 "status": "error",
    #                 "error": {"message": "message_id is required. Please use search_emails first to find email IDs."},
    #             }
    #
    #         # Get authentication token
    #         token = self._prepare_auth()
    #         if not token:
    #             return self.error_card("Authentication required. Please connect your email service.")
    #
    #         # Call email service
    #         email_data: dict = self.email_service.read(token=token, message_id=message_id)
    #
    #         return {
    #             "status": "success",
    #             "id": message_id,
    #             **email_data,
    #         }
    #
    #     except EmailAuthError as e:
    #         logger.error(f"Auth error in read_email: {e}")
    #         return self.error_card(f"Authentication failed: {e}")
    #     except Exception as e:
    #         logger.error(f"Error in read_email: {e}")
    #         return self.error_card(f"Failed to read email: {e}")

    def list_drafts(
        self,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        List draft emails with full details.

        This tool lists all draft emails in the mailbox with their subject, recipients, and snippets.
        No confirmation required.

        Args:
            max_results: Maximum number of drafts to return (default: 10)

        Returns:
            Dictionary with status and draft list:
            {
                "status": "success" | "error",
                "query": "in:draft",
                "drafts": [
                    {
                        "id": "draft123",
                        "subject": "Project Update",
                        "to": ["team@example.com"],
                        "from": "sender@example.com",
                        "from_name": "John Doe",  # Gmail only
                        "date": "2025-10-28T10:30:00-07:00",
                        "snippet": "Draft email preview...",
                        "labels": ["DRAFT"],
                        "is_unread": false,  # Gmail only
                        "gmail_link": "https://mail.google.com/mail/u/0/#drafts/draft123",  # Gmail only
                        "attachments": [{"filename": "doc.pdf", "mime_type": "application/pdf"}],  # Gmail only
                        "thread_id": "thread456"
                    },
                    ...
                ],
                "total_count": 3
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your email service.")

            # Search for draft message IDs
            message_ids: list[str] = self.email_service.search(token=token, query="in:draft", max_results=max_results)

            # Fetch details for each draft (same pattern as search_emails)
            drafts = []
            is_gmail = "gmail" in self.service_name.lower() or "google" in self.service_name.lower()

            for msg_id in message_ids:
                try:
                    email_data = self.email_service.read(token=token, message_id=msg_id)

                    # Use transformer for Gmail to get link data
                    if is_gmail:
                        link_data = transform_gmail_to_link_data(email_data)

                        # Extract "To" header from Gmail payload
                        to_header = ""
                        headers = email_data.get("payload", {}).get("headers", [])
                        for header in headers:
                            if header.get("name", "").lower() == "to":
                                to_header = header.get("value", "")
                                break

                        drafts.append(
                            {
                                "id": link_data.message_id,
                                "subject": link_data.subject,
                                "to": [to_header] if to_header else [],
                                "from": link_data.from_address,
                                "from_name": link_data.from_name,
                                "date": link_data.date.isoformat(),
                                "snippet": link_data.snippet,
                                "labels": link_data.labels,
                                "is_unread": link_data.is_unread,
                                "gmail_link": link_data.gmail_link,
                                "attachments": [
                                    {"filename": att.filename, "mime_type": att.mime_type}
                                    for att in link_data.attachments
                                ],
                                "thread_id": link_data.thread_id,
                            }
                        )
                    else:
                        # Fallback for non-Gmail providers (Microsoft, etc.)
                        drafts.append(
                            {
                                "id": msg_id,
                                "subject": email_data.get("subject", ""),
                                "to": email_data.get("to", []),
                                "from": email_data.get("from", ""),
                                "date": email_data.get("date", ""),
                                "snippet": email_data.get("snippet", ""),
                                "labels": email_data.get("labels", []),
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to read draft {msg_id}: {e}")
                    # Include partial data with error indicator
                    drafts.append({"id": msg_id, "error": str(e)})

            return {
                "status": "success",
                "query": "in:draft",
                "drafts": drafts,
                "total_count": len(drafts),
            }

        except EmailAuthError as e:
            logger.error(f"Auth error in list_drafts: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in list_drafts: {e}")
            return self.error_card(f"Failed to list drafts: {e}")

    def email_auth_required(self) -> Dict[str, Any]:
        """
        Display an authentication required message to the user.

        This method is called when the user attempts to initiate any email tool and user not
        authenticated their email service (Google Gmail or Microsoft Outlook).
        It informs the user that email authentication is required before they can
        create, view, or manage email.

        WHEN CALLED
        - Triggered by the agent when no email tokens are available

        USER EXPERIENCE
        The user will see a message indicating:
        - Email authentication is required to create or view emails
        - Instructions to connect their Google or Microsoft Calendar account
        - Available actions: "Connect Email"

        OUTPUT (JSON)
        Returns an email-auth-required card:
        {
            "card": "email-auth-required",
            "context": {
                "token_valid": false
            }
        }
        """

        self._prepare_auth(hard=False)
        return {
            "card": "email-auth-required",
            "context": dict(self.context),
        }
