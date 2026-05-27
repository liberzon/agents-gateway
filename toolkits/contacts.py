"""
Contacts Toolkit

This module provides the ContactsToolkit class for multi-provider
contact management with support for Google Contacts and Microsoft Contacts.

Usage:
    >>> from toolkits.contacts import ContactsToolkit
    >>> toolkit = ContactsToolkit(
    ...     user_id="user123",
    ...     service_name="google_contacts",
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
from workspace_suite import ContactsService
from workspace_suite.config import ProviderConfig
from workspace_suite.models import Contact, ContactResult
from workspace_suite.providers.google_contacts import GoogleContactsProvider
from workspace_suite.providers.microsoft_contacts import MicrosoftContactsProvider

logger = logging.getLogger(__name__)


# ---------------------------
# Exceptions
# ---------------------------
class ContactsAuthError(RuntimeError):
    """Exception raised when contacts authentication fails."""

    pass


# ---------------------------
# Contacts Toolkit
# ---------------------------
class ContactsToolkit(BaseToolkit):
    """
    AI Agent toolkit for contact management operations with multi-provider support.

    This toolkit provides intelligent contact management capabilities for AI agents,
    supporting both Google Contacts and Microsoft Contacts. It handles OAuth
    authentication, token management, contact CRUD operations, and provides graceful
    fallbacks when authentication is unavailable.

    ARCHITECTURE
    ============
    The toolkit follows a confirmation-based workflow where the AI agent proposes
    contact operations, the user reviews and confirms, and then the operation is executed.
    This prevents unwanted contact modifications and allows users to edit details
    before committing.

    Token Management:
    -----------------
    - Uses a shared TokenCache (toolkits.token_cache) for efficient token storage across instances
    - Supports multiple contact providers (Google, Microsoft) via service_name parameter
    - Tokens are cached with TTL-based expiration (default: 5 minutes)
    - Automatic token refresh and error handling with cooldown periods

    Authentication Flow:
    -------------------
    1. If user has valid token → toolkit provides contact management tools
    2. If no valid token → toolkit provides auth_required tool
    3. User authenticates via OAuth flow when prompted
    4. Subsequent requests automatically use authenticated service

    SUPPORTED SERVICES
    ==================
    - Google Contacts (service_name="google_contacts")
    - Microsoft Contacts (service_name="microsoft_contacts")

    TOOLS PROVIDED
    ==============
    When authenticated (auth=True):
    - create_contact: Create new contact (requires confirmation)
    - update_contact: Update contact fields (requires confirmation)
    - delete_contact: Delete contact permanently (requires confirmation)
    - list_contacts: List all contacts (no confirmation)
    - search_contacts: Search contacts by query (no confirmation)
    - error_card: Display error messages with retry options

    When not authenticated (auth=False):
    - auth_required: Prompt user to authenticate contacts service

    CONFIRMATION WORKFLOW
    =====================
    Write operations (create/update/delete) require confirmation:
    1. Agent calls operation with proposed details
    2. Run pauses and returns tool call details to client
    3. Client displays interactive form for user to review/edit
    4. User confirms, skips, or cancels
    5. Client sends confirmed tools via /chat/commit endpoint
    6. Agent resumes and executes the actual contacts API call
    7. Operation is executed and confirmation is returned

    USAGE EXAMPLES
    ==============
    Basic initialization:
        >>> toolkit = ContactsToolkit(
        ...     user_id="user123",
        ...     service_name="google_contacts",
        ...     auth=True
        ... )

    Multi-provider setup:
        >>> google_toolkit = ContactsToolkit(
        ...     user_id="user123",
        ...     service_name="google_contacts"
        ... )
        >>> microsoft_toolkit = ContactsToolkit(
        ...     user_id="user123",
        ...     service_name="microsoft_contacts"
        ... )

    No-auth fallback:
        >>> no_auth_toolkit = ContactsToolkit(
        ...     user_id="user123",
        ...     service_name="contacts",
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
        Contacts service identifier ("google_contacts", "microsoft_contacts", etc.)

    context : Dict[str, Any]
        Runtime context including token_valid status

    METHODS
    =======
    Public Tools:
    - create_contact(): Create new contact (requires confirmation)
    - update_contact(): Update contact fields (requires confirmation)
    - delete_contact(): Delete contact permanently (requires confirmation)
    - list_contacts(): List all contacts (no confirmation)
    - search_contacts(): Search contacts (no confirmation)
    - auth_required(): Prompt for contacts authentication
    - error_card(): Display error messages

    Internal Helpers:
    - _prepare_auth(): Manage OAuth token retrieval and validation

    ERROR HANDLING
    ==============
    - ContactsAuthError: Token fetch failures, expired tokens
    - HTTP errors: API quota limits, permission issues, network failures
    - Validation errors: Invalid contact data, missing required fields

    All errors are caught and returned as structured error cards with retry options.

    SECURITY
    ========
    - Tokens never exposed in logs or responses
    - OAuth scopes limited to contacts.read/write (no full account access)
    - User confirmation required before any contact modifications
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
        Initialize the ContactsToolkit.

        Args:
            user_id: User identifier for token lookup (tools_user_id)
            service_name: Contacts service name ("google_contacts", "microsoft_contacts", etc.)
            auth: Whether user is authenticated (determines which tools are available)
            fetch_token_func: Optional function to fetch access tokens. If not provided,
                            toolkit will attempt to import from parent module.
        """
        # Call BaseToolkit.__init__ which will call _initialize_service()
        BaseToolkit.__init__(self, user_id, service_name, auth, fetch_token_func)

        # Build tools list AFTER service is initialized (methods need self.contacts_service)
        tools_list: list = []
        confirmation_tools_list = []

        if auth:
            tools_list.append(self.create_contact)
            tools_list.append(self.update_contact)
            tools_list.append(self.delete_contact)
            tools_list.append(self.list_contacts)
            tools_list.append(self.search_contacts)
            confirmation_tools_list = ["create_contact", "update_contact", "delete_contact"]
        else:
            tools_list.append(self.contacts_auth_required)

        # Call Toolkit base class __init__ LAST with complete tools list
        Toolkit.__init__(
            self,
            name="ContactsToolkit",
            tools=tools_list,
            requires_confirmation_tools=confirmation_tools_list,
            show_result_tools=[],
            stop_after_tool_call_tools=([] if auth else ["contacts_auth_required"]),
        )

    def _initialize_service(self) -> None:
        """Initialize contacts service with appropriate provider."""
        config = ProviderConfig()

        if "google" in self.service_name.lower():
            provider: GoogleContactsProvider | MicrosoftContactsProvider = GoogleContactsProvider(config)
        elif "microsoft" in self.service_name.lower():
            provider = MicrosoftContactsProvider(config)  # type: ignore[assignment]
        else:
            # Default to Google
            provider = GoogleContactsProvider(config)

        self.contacts_service = ContactsService(provider)

    # ---------------------------
    # Tools
    # ---------------------------

    def create_contact(
        self,
        given_name: str,
        family_name: Optional[str] = None,
        emails: Optional[List[str]] = None,
        phones: Optional[List[str]] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new contact.

        This tool creates a new contact in the user's address book. It requires
        confirmation before execution.

        Args:
            given_name: Contact's first name (required)
            family_name: Contact's last name (optional)
            emails: List of email addresses (optional)
            phones: List of phone numbers (optional)
            company: Company name (optional)
            job_title: Job title (optional)

        Returns:
            Dictionary with status and contact details:
            {
                "status": "success" | "error",
                "resource_name": "people/c12345",
                "given_name": "John",
                "family_name": "Doe",
                "emails": ["john@example.com"],
                "phones": ["+1234567890"],
                "company": "Acme Inc",
                "job_title": "Engineer",
                "error": {...} (if status=error)
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your contacts service.")

            # Create contact object
            contact = Contact(
                given_name=given_name,
                family_name=family_name,
                emails=tuple(emails) if emails else (),
                phones=tuple(phones) if phones else (),
                company=company,
                job_title=job_title,
            )

            # Call contacts service
            result: ContactResult = self.contacts_service.create(token=token, contact=contact)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "resource_name": result.resource_name,
                    "given_name": given_name,
                    "family_name": family_name,
                    "emails": emails or [],
                    "phones": phones or [],
                    "company": company,
                    "job_title": job_title,
                }
            else:
                return {
                    "status": "error",
                    "error": result.error or {"message": "Failed to create contact"},
                }

        except ContactsAuthError as e:
            logger.error(f"Auth error in create_contact: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in create_contact: {e}")
            return self.error_card(f"Failed to create contact: {e}")

    def update_contact(
        self,
        resource_name: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        emails: Optional[List[str]] = None,
        phones: Optional[List[str]] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing contact.

        This tool updates fields of an existing contact. Only provided fields will be updated.
        Requires confirmation before execution.

        Args:
            resource_name: Contact resource identifier (e.g., "people/c12345")
            given_name: Updated first name (optional)
            family_name: Updated last name (optional)
            emails: Updated email addresses (optional)
            phones: Updated phone numbers (optional)
            company: Updated company name (optional)
            job_title: Updated job title (optional)

        Returns:
            Dictionary with status and updated contact details
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your contacts service.")

            # Build patch dictionary with only provided fields
            patch: dict[str, Any] = {}
            if given_name is not None:
                patch["given_name"] = given_name
            if family_name is not None:
                patch["family_name"] = family_name
            if emails is not None:
                patch["emails"] = emails  # type: ignore[assignment]
            if phones is not None:
                patch["phones"] = phones  # type: ignore[assignment]
            if company is not None:
                patch["company"] = company
            if job_title is not None:
                patch["job_title"] = job_title

            # Call contacts service
            result: ContactResult = self.contacts_service.update(token=token, resource_name=resource_name, patch=patch)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "resource_name": resource_name,
                    "updated_fields": list(patch.keys()),
                    "given_name": given_name,
                    "family_name": family_name,
                    "emails": emails,
                    "phones": phones,
                    "company": company,
                    "job_title": job_title,
                }
            else:
                return {
                    "status": "error",
                    "resource_name": resource_name,
                    "error": result.error or {"message": "Failed to update contact"},
                }

        except ContactsAuthError as e:
            logger.error(f"Auth error in update_contact: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in update_contact: {e}")
            return self.error_card(f"Failed to update contact: {e}")

    def delete_contact(
        self,
        resource_name: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        emails: Optional[List[str]] = None,
        phones: Optional[List[str]] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Delete a contact permanently.

        This tool permanently deletes a contact from the user's address book.
        Requires confirmation before execution.

        Args:
            resource_name: Contact resource identifier (e.g., "people/c12345")
            given_name: Deleted contact first name (optional)
            family_name: Deleted contact last name (optional)
            emails: Deleted contact email addresses (optional)
            phones: Deleted contact phone numbers (optional)
            company: Deleted contact company name (optional)
            job_title: Deleted contact job title (optional)

        Returns:
            Dictionary with status, deletion confirmation, and contact details:
            {
                "status": "success" | "error",
                "resource_name": "people/c12345",
                "message": "Contact deleted successfully",
                "given_name": "John",
                "family_name": "Doe",
                "emails": ["john@example.com"],
                "phones": ["+1234567890"],
                "company": "Acme Corp",
                "job_title": "Engineer"
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your contacts service.")

            # First, fetch contact details before deleting
            import httpx

            headers = {"Authorization": f"Bearer {token}"}
            params = {"personFields": "names,emailAddresses,phoneNumbers"}
            url = f"https://people.googleapis.com/v1/{resource_name}"

            client = httpx.Client(timeout=15.0)
            get_resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]

            # Initialize contact details (will be populated if fetch succeeds)
            contact_details: Dict[str, Any] = {}

            if get_resp.status_code == 200:
                person = get_resp.json()

                # Extract names
                names = person.get("names", [])
                given_name = names[0].get("givenName", "") if names else ""
                family_name = names[0].get("familyName", "") if names else ""

                # Extract emails
                email_objs = person.get("emailAddresses", [])
                emails = [e.get("value", "") for e in email_objs if e.get("value")]

                # Extract phones
                phone_objs = person.get("phoneNumbers", [])
                phones = [p.get("value", "") for p in phone_objs if p.get("value")]

                # Extract organization
                org_objs = person.get("organizations", [])
                company = org_objs[0].get("name", "") if org_objs else ""
                job_title = org_objs[0].get("title", "") if org_objs else ""

                contact_details = {
                    "given_name": given_name,
                    "family_name": family_name,
                    "emails": emails,
                    "phones": phones,
                    "company": company,
                    "job_title": job_title,
                }
            else:
                logger.warning(f"Failed to fetch contact details before deletion: {get_resp.status_code}")

            # Now delete the contact
            result: ContactResult = self.contacts_service.delete(token=token, resource_name=resource_name)

            # Return structured response
            if result.status == "success":
                return {
                    "status": "success",
                    "resource_name": resource_name,
                    "message": "Contact deleted successfully",
                    **contact_details,  # Include contact details if available
                }
            else:
                return {
                    "status": "error",
                    "resource_name": resource_name,
                    "error": result.error or {"message": "Failed to delete contact"},
                }

        except ContactsAuthError as e:
            logger.error(f"Auth error in delete_contact: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in delete_contact: {e}")
            return self.error_card(f"Failed to delete contact: {e}")

    def list_contacts(
        self,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """
        List all contacts from both 'My Contacts' and 'Other Contacts'.

        This tool lists contacts from the user's address book, including:
        - My Contacts: Contacts explicitly saved by the user
        - Other Contacts: Auto-saved contacts from Gmail interactions

        No confirmation required.

        Args:
            max_results: Maximum number of contacts to return per source (default: 100)

        Returns:
            Dictionary with status and merged contact list:
            {
                "status": "success" | "error",
                "contacts": [
                    {
                        "resource_name": "people/c12345",
                        "given_name": "John",
                        "family_name": "Doe",
                        "emails": ["john@example.com"],
                        "source": "my_contacts" | "other_contacts" | "both",
                        ...
                    },
                    ...
                ],
                "total_count": 42,
                "my_contacts_count": 25,
                "other_contacts_count": 20,
                "deduplicated_count": 3
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your contacts service.")

            # Fetch My Contacts using provider
            my_contacts_list, my_contacts_error = self.contacts_service.provider.fetch_contacts_raw(
                token=token, page_size=max_results
            )

            # Fetch Other Contacts using provider
            other_contacts_list, other_contacts_error = self.contacts_service.provider.fetch_other_contacts_raw(
                token=token, page_size=max_results
            )

            # If both failed, return error
            if my_contacts_error and other_contacts_error:
                return {
                    "status": "error",
                    "error": {
                        "message": "Failed to fetch contacts from both sources",
                        "my_contacts_error": my_contacts_error,
                        "other_contacts_error": other_contacts_error,
                    },
                }

            # Parse and merge contacts
            email_to_contact: Dict[str, Dict[str, Any]] = {}

            def parse_person(person: dict, source: str) -> Dict[str, Any]:
                # Extract names
                names = person.get("names", [])
                given_name = names[0].get("givenName", "") if names else ""
                family_name = names[0].get("familyName", "") if names else ""

                # Extract emails
                email_objs = person.get("emailAddresses", [])
                emails = [e.get("value", "") for e in email_objs if e.get("value")]

                # Extract phones
                phone_objs = person.get("phoneNumbers", [])
                phones = [p.get("value", "") for p in phone_objs if p.get("value")]

                # Extract organization
                org_objs = person.get("organizations", [])
                company = org_objs[0].get("name", "") if org_objs else ""
                job_title = org_objs[0].get("title", "") if org_objs else ""

                return {
                    "resource_name": person.get("resourceName", ""),
                    "given_name": given_name,
                    "family_name": family_name,
                    "full_name": f"{given_name} {family_name}".strip(),
                    "emails": emails,
                    "phones": phones,
                    "company": company,
                    "job_title": job_title,
                    "source": source,
                }

            # Process My Contacts first (higher priority)
            for person in my_contacts_list:
                contact = parse_person(person, "my_contacts")
                # Use first email as deduplication key
                if contact["emails"]:
                    primary_email = contact["emails"][0].lower()
                    email_to_contact[primary_email] = contact
                else:
                    # No email - add with resource_name as key
                    email_to_contact[contact["resource_name"]] = contact

            # Process Other Contacts (merge or add)
            for person in other_contacts_list:
                contact = parse_person(person, "other_contacts")
                if contact["emails"]:
                    primary_email = contact["emails"][0].lower()
                    if primary_email in email_to_contact:
                        # Mark as existing in both sources
                        email_to_contact[primary_email]["source"] = "both"
                    else:
                        email_to_contact[primary_email] = contact
                else:
                    # No email - add with resource_name as key
                    if contact["resource_name"] not in email_to_contact:
                        email_to_contact[contact["resource_name"]] = contact

            # Calculate counts
            total_fetched = len(my_contacts_list) + len(other_contacts_list)
            final_count = len(email_to_contact)
            deduplicated_count = total_fetched - final_count

            # Convert to list
            contacts = list(email_to_contact.values())

            return {
                "status": "success",
                "contacts": contacts,
                "total_count": final_count,
                "my_contacts_count": len(my_contacts_list),
                "other_contacts_count": len(other_contacts_list),
                "deduplicated_count": deduplicated_count,
            }

        except ContactsAuthError as e:
            logger.error(f"Auth error in list_contacts: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in list_contacts: {e}")
            return self.error_card(f"Failed to list contacts: {e}")

    def search_contacts(
        self,
        query: str,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """
        Search contacts by query in both 'My Contacts' and 'Other Contacts'.

        This tool searches contacts across all sources:
        - My Contacts: User's explicitly saved contacts
        - Other Contacts: Auto-saved contacts from Gmail

        No confirmation required.

        Args:
            query: Search query string (searches name, email, phone, etc.)
            max_results: Maximum number of results to return per source (default: 100)

        Returns:
            Dictionary with status and merged search results:
            {
                "status": "success" | "error",
                "query": "search query",
                "contacts": [
                    {
                        "resource_name": "people/c12345",
                        "given_name": "John",
                        "emails": ["john@example.com"],
                        "source": "my_contacts" | "other_contacts" | "both",
                        ...
                    },
                    ...
                ],
                "total_count": 15,
                "my_contacts_count": 10,
                "other_contacts_count": 8,
                "deduplicated_count": 3
            }
        """
        try:
            # Get authentication token
            token = self._prepare_auth()
            if not token:
                return self.error_card("Authentication required. Please connect your contacts service.")

            # Search My Contacts using provider
            my_contacts_results, my_contacts_error = self.contacts_service.provider.search_contacts_raw(
                token=token, query=query, page_size=max_results
            )

            # Search Other Contacts (via list + filter)
            # Note: Google doesn't provide direct search for otherContacts,
            # so we fetch all and filter client-side using the provider
            all_other_contacts, other_contacts_error = self.contacts_service.provider.fetch_other_contacts_raw(
                token=token, page_size=max_results
            )

            # Filter Other Contacts by query (case-insensitive substring match)
            other_contacts_results = []
            if not other_contacts_error:
                query_lower = query.lower()
                for person in all_other_contacts:
                    # Check if query matches name, email, or phone
                    names = person.get("names", [])
                    name_match = any(
                        query_lower in name.get("displayName", "").lower()
                        or query_lower in name.get("givenName", "").lower()
                        or query_lower in name.get("familyName", "").lower()
                        for name in names
                    )

                    emails = person.get("emailAddresses", [])
                    email_match = any(query_lower in email.get("value", "").lower() for email in emails)

                    phones = person.get("phoneNumbers", [])
                    phone_match = any(query_lower in phone.get("value", "").lower() for phone in phones)

                    if name_match or email_match or phone_match:
                        other_contacts_results.append(person)

            # If both failed, return error
            if my_contacts_error and other_contacts_error:
                return {
                    "status": "error",
                    "error": {
                        "message": "Failed to search contacts in both sources",
                        "my_contacts_error": my_contacts_error,
                        "other_contacts_error": other_contacts_error,
                    },
                }

            # Parse and merge results
            email_to_contact: Dict[str, Dict[str, Any]] = {}

            def parse_person(person: dict, source: str) -> Dict[str, Any]:
                # Extract names
                names = person.get("names", [])
                given_name = names[0].get("givenName", "") if names else ""
                family_name = names[0].get("familyName", "") if names else ""

                # Extract emails
                email_objs = person.get("emailAddresses", [])
                emails = [e.get("value", "") for e in email_objs if e.get("value")]

                # Extract phones
                phone_objs = person.get("phoneNumbers", [])
                phones = [p.get("value", "") for p in phone_objs if p.get("value")]

                # Extract organization
                org_objs = person.get("organizations", [])
                company = org_objs[0].get("name", "") if org_objs else ""
                job_title = org_objs[0].get("title", "") if org_objs else ""

                return {
                    "resource_name": person.get("resourceName", ""),
                    "given_name": given_name,
                    "family_name": family_name,
                    "full_name": f"{given_name} {family_name}".strip(),
                    "emails": emails,
                    "phones": phones,
                    "company": company,
                    "job_title": job_title,
                    "source": source,
                }

            # Process My Contacts results first (higher priority)
            for person in my_contacts_results:
                contact = parse_person(person, "my_contacts")
                if contact["emails"]:
                    primary_email = contact["emails"][0].lower()
                    email_to_contact[primary_email] = contact
                else:
                    email_to_contact[contact["resource_name"]] = contact

            # Process Other Contacts results (merge or add)
            for person in other_contacts_results:
                contact = parse_person(person, "other_contacts")
                if contact["emails"]:
                    primary_email = contact["emails"][0].lower()
                    if primary_email in email_to_contact:
                        # Mark as existing in both sources
                        email_to_contact[primary_email]["source"] = "both"
                    else:
                        email_to_contact[primary_email] = contact
                else:
                    if contact["resource_name"] not in email_to_contact:
                        email_to_contact[contact["resource_name"]] = contact

            # Calculate counts
            total_fetched = len(my_contacts_results) + len(other_contacts_results)
            final_count = len(email_to_contact)
            deduplicated_count = total_fetched - final_count

            # Convert to list
            contacts = list(email_to_contact.values())

            return {
                "status": "success",
                "query": query,
                "contacts": contacts,
                "total_count": final_count,
                "my_contacts_count": len(my_contacts_results),
                "other_contacts_count": len(other_contacts_results),
                "deduplicated_count": deduplicated_count,
            }

        except ContactsAuthError as e:
            logger.error(f"Auth error in search_contacts: {e}")
            return self.error_card(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error in search_contacts: {e}")
            return self.error_card(f"Failed to search contacts: {e}")

    def contacts_auth_required(self) -> Dict[str, Any]:
        """
        Display an authentication required message to the user.

        This method is called when the user attempts to initiate any contact tool and user not
        authenticated their contact service.
        It informs the user that contacts authentication is required before they can
        create, view, or manage contacts.

        WHEN CALLED
        - Triggered by the agent when no contacts tokens are available

        USER EXPERIENCE
        The user will see a message indicating:
        - Contacts authentication is required to create or view emails
        - Instructions to connect their Google or Microsoft contacts account
        - Available actions: "Connect Contacts"

        OUTPUT (JSON)
        Returns an contacts-auth-required card:
        {
            "card": "contacts-auth-required",
            "context": {
                "token_valid": false
            }
        }
        """
        self._prepare_auth(hard=False)
        return {
            "card": "contacts-auth-required",
            "context": dict(self.context),
        }
