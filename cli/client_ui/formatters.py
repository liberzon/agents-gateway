"""
Result Formatters for CLI Client

This module contains Rich-based formatters for displaying tool results
in a beautiful, user-friendly format.
"""

import json
from datetime import datetime
from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class ResultFormatter:
    """
    Formats tool results using Rich library for beautiful console output.
    Provides tool-specific formatters and generic fallback.
    """

    def __init__(self):
        self.console = Console()

    def format_result(self, tool: Dict[str, Any], result: Any) -> None:
        """
        Main entry point for formatting tool results.

        Args:
            tool: The complete tool object containing tool_name, args, etc.
            result: The result data to format (typically a dict)
        """
        if result is None:
            return

        tool_name = tool.get("tool_name") or tool.get("name") or "Unknown"

        # Ignore get_chat_history tools (internal system tools)
        if tool_name == "get_chat_history":
            return

        # Check if result is an error card (has "card": "error")
        if isinstance(result, dict) and result.get("card") == "error":
            self._format_error_card(tool, result)
            return

        # Check if result has status=error (API error responses)
        if isinstance(result, dict) and result.get("status") == "error":
            self._format_error_response(tool, result)
            return

        # Route to tool-specific formatters
        # Calendar tools
        if tool_name == "schedule_meeting":
            self._format_schedule_meeting(tool, result)
        elif tool_name == "schedule_meeting_find_time":
            self._format_schedule_meeting_find_time(tool, result)
        elif tool_name == "cancel_meeting":
            self._format_cancel_meeting(tool, result)
        elif tool_name == "list_events":
            self._format_list_events(tool, result)
        # Contacts tools
        elif tool_name == "create_contact":
            self._format_create_contact(tool, result)
        elif tool_name == "update_contact":
            self._format_update_contact(tool, result)
        elif tool_name == "delete_contact":
            self._format_delete_contact(tool, result)
        elif tool_name == "list_contacts":
            self._format_list_contacts(tool, result)
        elif tool_name == "search_contacts":
            self._format_search_contacts(tool, result)
        # Drive tools
        elif tool_name == "read_file":
            self._format_read_file(tool, result)
        elif tool_name == "upload_file":
            self._format_upload_file(tool, result)
        elif tool_name == "create_folder":
            self._format_create_folder(tool, result)
        elif tool_name == "list_files":
            self._format_list_files(tool, result)
        elif tool_name == "delete_file":
            self._format_delete_file(tool, result)
        # Email tools
        elif tool_name == "send_email":
            self._format_send_email(tool, result)
        elif tool_name == "create_draft":
            self._format_create_draft(tool, result)
        elif tool_name == "send_draft":
            self._format_send_draft(tool, result)
        elif tool_name == "search_emails":
            self._format_search_emails(tool, result)
        elif tool_name == "read_email":
            self._format_read_email(tool, result)
        elif tool_name == "list_drafts":
            self._format_list_drafts(tool, result)
        elif tool_name == "trash_email":
            self._format_trash_email(tool, result)
        elif tool_name == "delete_email_permanently":
            self._format_delete_email_permanently(tool, result)
        elif tool_name == "modify_labels":
            self._format_modify_labels(tool, result)
        # Generic tools (auth_required with service-specific names)
        elif tool_name in (
            "calendar_auth_required",
            "email_auth_required",
            "contacts_auth_required",
            "drive_auth_required",
            "auth_required",
        ):
            self._format_auth_required(tool, result)
        else:
            # Generic fallback for unknown tools
            self._format_generic(tool, result)

    def _format_schedule_meeting(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format schedule_meeting tool results with a beautiful card-style display."""
        # Extract meeting details from result
        meeting_title = result.get("summary") or result.get("title") or "Meeting"
        meeting_id = result.get("id") or result.get("event_id") or "N/A"
        start_time = result.get("start") or result.get("start_time") or "TBD"
        end_time = result.get("end") or result.get("end_time") or "TBD"
        attendees = result.get("attendees") or []
        meeting_link = (
            result.get("hangoutLink")
            or result.get("hangout_link")
            or result.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri")
        )
        html_link = result.get("htmlLink") or result.get("html_link")
        status = result.get("status", "confirmed")

        # Create the main content
        content = Text()

        # Success message
        if status == "confirmed":
            content.append("✓ ", style="bold green")
            content.append("Your meeting has been successfully scheduled and invitations sent.\n\n", style="green")
        else:
            content.append("Meeting created with status: ", style="yellow")
            content.append(f"{status}\n\n", style="bold yellow")

        # Meeting title
        content.append(f"{meeting_title}\n", style="bold cyan")

        # Meeting ID
        content.append("Meeting ID: ", style="dim")
        content.append(f"{meeting_id}\n\n", style="bold")

        # Time information
        content.append("🕒 ", style="bold")
        content.append(f"{start_time}", style="bold white")
        if end_time and end_time != "TBD":
            content.append(f" - {end_time}\n", style="bold white")
        else:
            content.append("\n", style="bold white")

        # Attendees
        attendee_count = len(attendees) if isinstance(attendees, list) else 0
        if attendee_count > 0:
            content.append(f"\n👥 {attendee_count} attendee{'s' if attendee_count != 1 else ''} invited\n", style="")

        # Meeting link (clickable if available)
        if meeting_link:
            content.append("\n🔗 ", style="bold")
            content.append(meeting_link, style="link " + meeting_link)
            content.append("\n")

        # Open in Calendar link (two lines below meeting link)
        if html_link:
            content.append("\n\n📅 ", style="bold")
            content.append("Open in Calendar", style="bold blue link " + html_link)
            content.append("\n")

        # Create action buttons section
        actions = Text("\n")
        actions.append("📋 Copy Details", style="bold blue")
        actions.append(" • ", style="dim")
        actions.append("❌ Cancel Meeting", style="bold red")

        content.append(actions)

        # Display in a panel with green border for success
        border_color = "green" if status == "confirmed" else "yellow"
        self.console.print(
            Panel(
                content,
                title="[bold white]Meeting Scheduled[/bold white]",
                title_align="left",
                border_style=border_color,
                padding=(1, 2),
            )
        )

    def _format_schedule_meeting_find_time(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format schedule_meeting_find_time results with available time slots."""
        # Extract meeting details
        meeting_title = result.get("meeting_title") or result.get("title") or result.get("summary") or "your meeting"
        suggested_times = result.get("suggested_times") or result.get("available_times") or []
        total_count = result.get("total_count") or len(suggested_times)

        # Limit to first 5 slots
        display_slots = suggested_times[:5] if len(suggested_times) > 5 else suggested_times
        has_more = len(suggested_times) > 5

        # Create the main content
        content = Text()

        # Header message
        content.append(f"Found {total_count} available slot{'s' if total_count != 1 else ''} for ", style="")
        content.append(f"{meeting_title}", style="bold cyan")
        content.append(":\n\n", style="")

        # Display each time slot
        for idx, slot in enumerate(display_slots):
            # Extract slot details
            start = slot.get("start") or slot.get("start_time") or ""
            end = slot.get("end") or slot.get("end_time") or ""
            available_count = slot.get("available_count") or slot.get("attendees_available")
            total_attendees = slot.get("total_attendees") or slot.get("total_count")
            is_optimal = slot.get("is_optimal") or slot.get("optimal") or False

            # Format the time display
            try:
                # Try to parse and format the date/time nicely
                if isinstance(start, str):
                    # Handle ISO format or other formats
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    day_name = start_dt.strftime("%A") if start_dt.date() != datetime.now().date() else "Today"
                    if (start_dt.date() - datetime.now().date()).days == 1:
                        day_name = "Tomorrow"
                    time_str = start_dt.strftime("%I:%M %p").lstrip("0")
                    if end:
                        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                        end_str = end_dt.strftime("%I:%M %p").lstrip("0")
                        time_display = f"{day_name} • {time_str} - {end_str}"
                    else:
                        time_display = f"{day_name} • {time_str}"
                else:
                    time_display = f"{start} - {end}" if end else str(start)
            except Exception:
                # Fallback to raw display
                time_display = f"{start} - {end}" if end else str(start)

            # Time slot line
            content.append(f"{time_display}\n", style="bold white")

            # Availability line
            if available_count is not None and total_attendees is not None:
                content.append(f"{available_count}/{total_attendees} available", style="dim")
            else:
                content.append("Available", style="dim")

            # Optimal badge
            if is_optimal:
                content.append("  •  ", style="dim")
                content.append("Optimal", style="bold green")

            content.append("\n", style="")

            # Select action
            content.append("Select", style="bold blue")
            content.append("\n\n", style="")

        # Add action buttons at the bottom
        actions = Text("\n")
        if has_more:
            actions.append("📋 Show More Times", style="bold blue")
            actions.append(" • ", style="dim")
        actions.append("⏱ Different Duration", style="bold blue")

        content.append(actions)

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold cyan]📅 Available Meeting Times[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _format_cancel_meeting(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format cancel_meeting tool results with a confirmation display."""
        # Extract cancellation details from result
        status = result.get("status", "unknown")
        event_id = result.get("event_id") or result.get("id") or "Unknown"
        summary = result.get("summary") or result.get("title")
        cancelled_at = result.get("cancelled_at") or result.get("updated")
        error_msg = result.get("error")

        # Create the main content
        content = Text()

        # Success or failure message
        if status == "success" or status == "cancelled":
            content.append("✓ ", style="bold green")
            content.append("Meeting successfully cancelled\n\n", style="green")
            border_color = "green"
        else:
            content.append("✗ ", style="bold red")
            content.append("Failed to cancel meeting\n\n", style="red")
            border_color = "red"

        # Event ID
        content.append("Event ID: ", style="dim")
        content.append(f"{event_id}\n", style="bold")

        # Meeting title if available
        if summary:
            content.append("Meeting: ", style="dim")
            content.append(f"{summary}\n", style="")

        # Timestamp if available
        if cancelled_at:
            content.append("Cancelled at: ", style="dim")
            content.append(f"{cancelled_at}\n", style="")

        # Error message if present
        if error_msg:
            content.append("\n", style="")
            content.append("Error: ", style="bold red")
            content.append(f"{error_msg}\n", style="red")

        # Notification info for success
        if status == "success" or status == "cancelled":
            content.append("\n", style="")
            content.append("All attendees have been notified of the cancellation.", style="dim italic")

        # Display in a panel
        self.console.print(
            Panel(
                content,
                title="[bold white]Meeting Cancellation[/bold white]",
                title_align="left",
                border_style=border_color,
                padding=(1, 2),
            )
        )

    def _format_auth_required(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format auth_required tool results with a beautiful authorization prompt."""
        # Determine which calendar service (could be inferred from context or made generic)
        # For now, we'll make it generic but visually appealing
        service_name = "Calendar Service"
        service_icon = "📅"

        # Create the main content
        content = Text()

        # Title with icon
        content.append("To schedule meetings and check availability, I need access to your calendar.\n\n", style="")

        # Service section
        content.append(f"{service_icon} ", style="bold")
        content.append(f"{service_name}\n", style="bold cyan")
        content.append("Connect your calendar to enable scheduling\n\n", style="dim")

        # Permissions/Features list
        content.append("This will allow me to:\n", style="bold")
        content.append("• Check your availability\n", style="")
        content.append("• Schedule meetings automatically\n", style="")
        content.append("• Send calendar invitations\n", style="")
        content.append("• Avoid scheduling conflicts\n", style="")

        # Display in a panel with yellow/orange border to indicate action needed
        self.console.print(
            Panel(
                content,
                title="[bold yellow]⚠ Calendar Access Required[/bold yellow]",
                title_align="left",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def _format_error_card(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format error card results with a clear error display."""
        # Extract error details
        error_message = result.get("message", "An unknown error occurred")
        context = result.get("context", {})

        # Create the main content
        content = Text()

        # Error icon and message
        content.append("✗ ", style="bold red")
        content.append("Operation Failed\n\n", style="bold red")

        # Error message
        content.append(error_message, style="white")

        # Context information (if available and useful)
        if context:
            content.append("\n\n", style="")
            # Show relevant context info
            if "token_valid" in context:
                token_status = "valid" if context["token_valid"] else "invalid"
                content.append("Authentication: ", style="dim")
                content.append(f"{token_status}\n", style="green" if context["token_valid"] else "red")

            # Show other context fields if present
            for key, value in context.items():
                if key != "token_valid" and value is not None:
                    content.append(f"{key}: ", style="dim")
                    content.append(f"{value}\n", style="white")

        # Display in a panel with red border to indicate error
        self.console.print(
            Panel(content, title="[bold red]⚠ Error[/bold red]", title_align="left", border_style="red", padding=(1, 2))
        )

    def _format_error_response(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format API error responses (status=error) with detailed error information."""
        tool_name = tool.get("tool_name") or tool.get("name") or "Unknown"

        # Extract error details from nested structure
        error_data = result.get("error", {})

        # Handle nested error structure (e.g., Google Calendar API errors)
        if isinstance(error_data, dict) and "error" in error_data:
            nested_error = error_data["error"]
            error_code = nested_error.get("code")
            error_message = nested_error.get("message", "An error occurred")
            error_details = nested_error.get("errors", [])
        else:
            # Simple error structure
            error_code = error_data.get("code")
            error_message = error_data.get("message") or error_data.get("details", "An error occurred")
            error_details = []

        # Create the main content
        content = Text()

        # Error icon and header
        content.append("✗ ", style="bold red")
        content.append(f"{tool_name.replace('_', ' ').title()} Failed\n\n", style="bold red")

        # Error message
        content.append(error_message, style="white")
        content.append("\n\n", style="")

        # Error code if present
        if error_code:
            content.append("Error Code: ", style="dim")
            content.append(f"{error_code}\n", style="bold red")

        # Detailed error information
        if error_details:
            content.append("\nDetails:\n", style="dim")
            for detail in error_details:
                reason = detail.get("reason", "")
                message = detail.get("message", "")

                if reason:
                    content.append("  • ", style="")
                    content.append(f"{reason}", style="yellow")
                    if message and message != error_message:
                        content.append(f": {message}", style="")
                    content.append("\n", style="")

        # Additional context from result
        context_fields = ["summary", "start", "end", "location", "event_id"]
        has_context = False
        context_text = Text()

        for field in context_fields:
            value = result.get(field)
            if value:
                if not has_context:
                    has_context = True
                    context_text.append("\nContext:\n", style="dim")
                context_text.append(f"  {field}: ", style="dim")
                context_text.append(f"{value}\n", style="")

        if has_context:
            content.append(context_text)

        # Display in a panel with red border
        self.console.print(
            Panel(
                content,
                title="[bold red]⚠ API Error[/bold red]",
                title_align="left",
                border_style="red",
                padding=(1, 2),
            )
        )

    def _format_list_events(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format list_events tool results with a beautiful calendar view."""
        # Extract event list and metadata
        events = result.get("events") or result.get("items") or []
        total_count = result.get("total_count") or len(events)
        query = result.get("query") or result.get("summary")
        date_range = result.get("range") or result.get("time_range") or result.get("date_range")
        calendar_name = result.get("calendar") or result.get("calendar_name") or "Calendar"

        # Create the main content
        content = Text()

        # Header with calendar name and count
        content.append(f"📅 {calendar_name}\n", style="bold cyan")

        if query:
            content.append(f"Search: {query}\n", style="dim")

        if date_range:
            content.append(f"Period: {date_range}\n", style="dim")

        content.append(f"\n{total_count} event{'s' if total_count != 1 else ''} found\n\n", style="")

        # Display events
        if not events:
            content.append("No events scheduled for this period.\n", style="dim italic")
        else:
            for idx, event in enumerate(events):
                # Extract event details with multiple possible field names
                summary = event.get("summary") or event.get("title") or event.get("name") or "Untitled Event"
                start = event.get("start") or event.get("start_time") or event.get("startDateTime")
                end = event.get("end") or event.get("end_time") or event.get("endDateTime")
                location = event.get("location")
                attendees = event.get("attendees") or []
                event_url = event.get("htmlLink") or event.get("html_link") or event.get("event_url")
                status = event.get("status") or "confirmed"
                organizer = event.get("organizer", {}).get("email") or event.get("organizer_email")
                is_all_day = event.get("all_day") or event.get("allDay") or False

                # Format datetime display
                try:
                    if isinstance(start, dict):
                        # Google Calendar format: {"dateTime": "...", "timeZone": "..."}
                        start_str = start.get("dateTime") or start.get("date")
                    else:
                        start_str = start

                    if start_str:
                        # Parse and format the datetime
                        if "T" in str(start_str):
                            start_dt = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))

                            # Determine day label
                            today = datetime.now().date()
                            start_date = start_dt.date()

                            if start_date == today:
                                day_label = "Today"
                            elif (start_date - today).days == 1:
                                day_label = "Tomorrow"
                            elif (start_date - today).days == -1:
                                day_label = "Yesterday"
                            elif (start_date - today).days < 7 and (start_date - today).days > 0:
                                day_label = start_dt.strftime("%A")  # Weekday name
                            else:
                                day_label = start_dt.strftime("%b %d")  # e.g., "Oct 22"

                            # Format time
                            if is_all_day:
                                time_display = f"{day_label} • All Day"
                            else:
                                time_str = start_dt.strftime("%I:%M %p").lstrip("0")

                                # Add end time if available
                                if end:
                                    if isinstance(end, dict):
                                        end_str = end.get("dateTime") or end.get("date")
                                    else:
                                        end_str = end

                                    if end_str and "T" in str(end_str):
                                        end_dt = datetime.fromisoformat(str(end_str).replace("Z", "+00:00"))
                                        end_time_str = end_dt.strftime("%I:%M %p").lstrip("0")
                                        time_display = f"{day_label} • {time_str} - {end_time_str}"
                                    else:
                                        time_display = f"{day_label} • {time_str}"
                                else:
                                    time_display = f"{day_label} • {time_str}"
                        else:
                            # Just a date, treat as all-day
                            time_display = f"{start_str} • All Day"
                    else:
                        time_display = "Time TBD"
                except Exception:
                    # Fallback to raw display
                    time_display = f"{start}"

                # Event status indicator
                if status == "cancelled":
                    status_icon = "✗"
                    status_style = "strike dim red"
                elif status == "tentative":
                    status_icon = "?"
                    status_style = "dim yellow"
                else:
                    status_icon = "•"
                    status_style = ""

                # Event title line
                content.append(f"{status_icon} ", style="bold " + status_style if status_style else "bold")
                content.append(f"{summary}\n", style="bold white " + status_style if status_style else "bold white")

                # Time line
                content.append(f"  {time_display}\n", style="dim " + status_style if status_style else "dim")

                # Location line (if present)
                if location:
                    content.append(f"  📍 {location}\n", style="dim " + status_style if status_style else "dim")

                # Attendees count (if present)
                attendee_count = len(attendees) if isinstance(attendees, list) else 0
                if attendee_count > 0:
                    content.append(
                        f"  👥 {attendee_count} attendee{'s' if attendee_count != 1 else ''}",
                        style="dim " + status_style if status_style else "dim",
                    )
                    if organizer:
                        content.append(
                            f" • Organized by {organizer}", style="dim " + status_style if status_style else "dim"
                        )
                    content.append("\n")

                # Event link (if present)
                if event_url:
                    content.append("  ", style="")
                    content.append("View Details", style="bold blue link " + event_url)
                    content.append("\n")

                # Add spacing between events (except last one)
                if idx < len(events) - 1:
                    content.append("\n")

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold cyan]📅 Calendar Events[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # ---------------------------
    # Contacts Formatters
    # ---------------------------

    def _format_create_contact(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format create_contact tool results with contact card display."""
        # Extract contact details
        given_name = result.get("given_name") or "Unknown"
        family_name = result.get("family_name") or ""
        emails = result.get("emails") or []
        phones = result.get("phones") or []
        company = result.get("company")
        job_title = result.get("job_title")
        resource_name = result.get("resource_name") or "N/A"

        # Create full name
        full_name = f"{given_name} {family_name}".strip()

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("Contact created successfully\n\n", style="green")

        # Contact name
        content.append(f"{full_name}\n", style="bold cyan")

        # Job title and company
        if job_title or company:
            if job_title and company:
                content.append(f"{job_title} at {company}\n\n", style="dim")
            elif job_title:
                content.append(f"{job_title}\n\n", style="dim")
            else:
                content.append(f"{company}\n\n", style="dim")

        # Emails
        if emails:
            content.append("📧 Email", style="bold")
            if len(emails) > 1:
                content.append("s", style="bold")
            content.append(":\n", style="bold")
            for email in emails:
                content.append(f"  {email}\n", style="")

        # Phones
        if phones:
            content.append("\n📞 Phone", style="bold")
            if len(phones) > 1:
                content.append("s", style="bold")
            content.append(":\n", style="bold")
            for phone in phones:
                content.append(f"  {phone}\n", style="")

        # Resource ID
        content.append("\n", style="")
        content.append("ID: ", style="dim")
        content.append(f"{resource_name}\n", style="")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ Contact Created[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_update_contact(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format update_contact tool results with update confirmation."""
        resource_name = result.get("resource_name") or "Unknown"
        updated_fields = result.get("updated_fields") or []

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("Contact updated successfully\n\n", style="green")

        # Contact ID
        content.append("Contact: ", style="dim")
        content.append(f"{resource_name}\n\n", style="bold")

        # Updated fields
        if updated_fields:
            content.append("Updated fields:\n", style="bold")
            for field in updated_fields:
                field_value = result.get(field)
                if field_value:
                    content.append(f"  • {field}: ", style="")
                    content.append(f"{field_value}\n", style="cyan")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ Contact Updated[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_delete_contact(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format delete_contact tool results with deletion confirmation."""
        resource_name = result.get("resource_name") or "Unknown"
        message = result.get("message") or "Contact deleted"

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append(f"{message}\n\n", style="green")

        # Contact ID
        content.append("Contact: ", style="dim")
        content.append(f"{resource_name}\n", style="bold")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ Contact Deleted[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_list_contacts(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format list_contacts tool results with contact list display."""
        contacts = result.get("contacts") or []
        total_count = result.get("total_count") or len(contacts)

        # Create the main content
        content = Text()

        # Header
        content.append("👥 Contacts\n\n", style="bold cyan")
        content.append(f"{total_count} contact{'s' if total_count != 1 else ''} found\n\n", style="")

        # Display contacts
        if not contacts:
            content.append("No contacts found.\n", style="dim italic")
        else:
            for idx, contact in enumerate(contacts):
                # Extract contact details
                full_name = (
                    contact.get("full_name")
                    or f"{contact.get('given_name', '')} {contact.get('family_name', '')}".strip()
                    or "Unknown"
                )
                emails = contact.get("emails") or []
                phones = contact.get("phones") or []
                company = contact.get("company")
                job_title = contact.get("job_title")

                # Contact name
                content.append(f"• {full_name}\n", style="bold white")

                # Job title and company
                if job_title or company:
                    content.append("  ", style="")
                    if job_title and company:
                        content.append(f"{job_title} at {company}\n", style="dim")
                    elif job_title:
                        content.append(f"{job_title}\n", style="dim")
                    else:
                        content.append(f"{company}\n", style="dim")

                # Emails
                if emails:
                    for email in emails:
                        content.append(f"  📧 {email}\n", style="")

                # Phones
                if phones:
                    for phone in phones:
                        content.append(f"  📞 {phone}\n", style="")

                # Add spacing between contacts (except last one)
                if idx < len(contacts) - 1:
                    content.append("\n")

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold cyan]👥 Contacts[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _format_search_contacts(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format search_contacts tool results with search results display."""
        query = result.get("query") or ""
        contacts = result.get("contacts") or []
        total_count = result.get("total_count") or len(contacts)

        # Create the main content
        content = Text()

        # Header with search query
        content.append("🔍 Contact Search\n", style="bold cyan")
        content.append(f"Query: {query}\n\n", style="dim")
        content.append(f"{total_count} result{'s' if total_count != 1 else ''}\n\n", style="")

        # Display contacts
        if not contacts:
            content.append("No contacts found matching your search.\n", style="dim italic")
        else:
            for idx, contact in enumerate(contacts):
                # Extract contact details
                full_name = (
                    contact.get("full_name")
                    or f"{contact.get('given_name', '')} {contact.get('family_name', '')}".strip()
                    or "Unknown"
                )
                emails = contact.get("emails") or []
                phones = contact.get("phones") or []
                company = contact.get("company")
                job_title = contact.get("job_title")

                # Contact name
                content.append(f"• {full_name}\n", style="bold white")

                # Job title and company
                if job_title or company:
                    content.append("  ", style="")
                    if job_title and company:
                        content.append(f"{job_title} at {company}\n", style="dim")
                    elif job_title:
                        content.append(f"{job_title}\n", style="dim")
                    else:
                        content.append(f"{company}\n", style="dim")

                # Emails
                if emails:
                    for email in emails:
                        content.append(f"  📧 {email}\n", style="")

                # Phones
                if phones:
                    for phone in phones:
                        content.append(f"  📞 {phone}\n", style="")

                # Add spacing between contacts (except last one)
                if idx < len(contacts) - 1:
                    content.append("\n")

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold cyan]🔍 Search Results[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # ---------------------------
    # Drive Formatters
    # ---------------------------

    def _format_read_file(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format read_file tool results with file indexing confirmation."""
        file_name = result.get("file_name") or result.get("name") or "Unknown"
        file_id = result.get("file_id") or result.get("id") or "Unknown"
        knowledge_entry_id = result.get("knowledge_entry_id")
        content_type = result.get("content_type")

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("File Indexed in Knowledge Base\n\n", style="green")

        # File name
        content.append(f"📄 {file_name}\n", style="bold cyan")

        # File details
        content.append("\nFile ID: ", style="dim")
        content.append(f"{file_id}\n", style="")

        if content_type:
            content.append("Type: ", style="dim")
            content.append(f"{content_type}\n", style="")

        if knowledge_entry_id:
            content.append("Knowledge Entry: ", style="dim")
            content.append(f"{knowledge_entry_id}\n", style="")

        # Info message
        content.append("\n", style="")
        content.append("💡 ", style="bold")
        content.append("File content has been indexed and can now be queried by the agent", style="dim")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ File Read & Indexed[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_upload_file(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format upload_file tool results with file upload confirmation."""
        file_id = result.get("id") or "Unknown"
        file_name = result.get("name") or "Untitled"
        web_view_link = result.get("web_view_link")

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("File uploaded successfully\n\n", style="green")

        # File name
        content.append(f"{file_name}\n", style="bold cyan")

        # File ID
        content.append("\nFile ID: ", style="dim")
        content.append(f"{file_id}\n", style="")

        # View link
        if web_view_link:
            content.append("\n📁 ", style="bold")
            content.append("View in Drive", style="bold blue link " + web_view_link)
            content.append("\n")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ File Uploaded[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_create_folder(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format create_folder tool results with folder creation confirmation."""
        folder_id = result.get("id") or "Unknown"
        folder_name = result.get("name") or "Untitled"
        web_view_link = result.get("web_view_link")

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("Folder created successfully\n\n", style="green")

        # Folder name
        content.append(f"📁 {folder_name}\n", style="bold cyan")

        # Folder ID
        content.append("\nFolder ID: ", style="dim")
        content.append(f"{folder_id}\n", style="")

        # View link
        if web_view_link:
            content.append("\n📁 ", style="bold")
            content.append("Open Folder", style="bold blue link " + web_view_link)
            content.append("\n")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ Folder Created[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_list_files(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format list_files tool results with file list display."""
        files = result.get("files") or []
        total_count = result.get("total_count") or len(files)
        query = result.get("query")
        message = result.get("message")  # Helpful message when no files found

        # Create the main content
        content = Text()

        # Header
        content.append("📁 Drive Files\n", style="bold cyan")
        if query:
            content.append(f"Search: {query}\n", style="dim")
        content.append(f"\n{total_count} file{'s' if total_count != 1 else ''} found\n\n", style="")

        # Display files
        if not files:
            content.append("No files found.\n\n", style="dim italic")
            # Display helpful message if available
            if message:
                content.append(message, style="yellow")
        else:
            for idx, file in enumerate(files):
                file_id = file.get("id") or "Unknown"
                file_name = file.get("name") or "Untitled"
                web_view_link = file.get("web_view_link")

                # File line
                content.append(f"📄 {file_name}\n", style="bold white")
                content.append(f"  ID: {file_id}\n", style="dim")

                # View link
                if web_view_link:
                    content.append("  ", style="")
                    content.append("View", style="bold blue link " + web_view_link)
                    content.append("\n")

                # Add spacing between files (except last one)
                if idx < len(files) - 1:
                    content.append("\n")

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold cyan]📁 Drive Files[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _format_delete_file(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format delete_file tool results with deletion confirmation."""
        file_id = result.get("id") or result.get("file_id") or "Unknown"
        message = result.get("message") or "File deleted"

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append(f"{message}\n\n", style="green")

        # File ID
        content.append("File ID: ", style="dim")
        content.append(f"{file_id}\n", style="bold")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ File Deleted[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    # ---------------------------
    # Email Formatters
    # ---------------------------

    def _format_send_email(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format send_email tool results with email sent confirmation."""
        email_id = result.get("id") or "Unknown"
        thread_id = result.get("thread_id")
        to = result.get("to") or []
        subject = result.get("subject") or "No subject"

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("Email sent successfully\n\n", style="green")

        # Subject
        content.append(f"{subject}\n", style="bold cyan")

        # Recipients
        content.append("\n📧 To: ", style="bold")
        content.append(f"{', '.join(to)}\n", style="")

        # Message ID
        content.append("\nMessage ID: ", style="dim")
        content.append(f"{email_id}\n", style="")

        # Thread ID
        if thread_id:
            content.append("Thread ID: ", style="dim")
            content.append(f"{thread_id}\n", style="")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ Email Sent[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_create_draft(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format create_draft tool results with draft creation confirmation."""
        draft_id = result.get("id") or "Unknown"
        to = result.get("to") or []
        subject = result.get("subject") or "No subject"

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("Draft created successfully\n\n", style="green")

        # Subject
        content.append(f"{subject}\n", style="bold cyan")

        # Recipients
        content.append("\n📧 To: ", style="bold")
        content.append(f"{', '.join(to)}\n", style="")

        # Draft ID
        content.append("\nDraft ID: ", style="dim")
        content.append(f"{draft_id}\n", style="")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ Draft Created[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_search_emails(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format search_emails tool results with search results display."""
        query = result.get("query") or ""
        message_ids = result.get("message_ids") or []
        total_count = result.get("total_count") or len(message_ids)

        # Create the main content
        content = Text()

        # Header with search query
        content.append("🔍 Email Search\n", style="bold cyan")
        content.append(f"Query: {query}\n\n", style="dim")
        content.append(f"{total_count} message{'s' if total_count != 1 else ''} found\n\n", style="")

        # Display message IDs
        if not message_ids:
            content.append("No emails found matching your search.\n", style="dim italic")
        else:
            for idx, msg_id in enumerate(message_ids[:10]):  # Limit to first 10
                content.append(f"• {msg_id}\n", style="")

            if len(message_ids) > 10:
                content.append(f"\n... and {len(message_ids) - 10} more\n", style="dim italic")

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold cyan]🔍 Search Results[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _format_read_email(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format read_email tool results with email content display."""
        email_id = result.get("id") or "Unknown"
        subject = result.get("subject") or "No subject"
        from_addr = result.get("from") or "Unknown sender"
        to_addrs = result.get("to") or []
        body = result.get("body") or result.get("snippet") or "No content"

        # Create the main content
        content = Text()

        # Subject
        content.append(f"{subject}\n\n", style="bold cyan")

        # From
        content.append("From: ", style="bold")
        content.append(f"{from_addr}\n", style="")

        # To
        if to_addrs:
            content.append("To: ", style="bold")
            if isinstance(to_addrs, list):
                content.append(f"{', '.join(to_addrs)}\n", style="")
            else:
                content.append(f"{to_addrs}\n", style="")

        # Body
        content.append("\n" + "─" * 60 + "\n\n", style="dim")
        content.append(f"{body}\n", style="")

        # Display in a panel with blue border
        self.console.print(
            Panel(
                content,
                title=f"[bold white]📧 Email: {email_id}[/bold white]",
                title_align="left",
                border_style="blue",
                padding=(1, 2),
            )
        )

    def _format_send_draft(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format send_draft tool results with draft sent confirmation."""
        email_id = result.get("id") or "Unknown"
        draft_id = result.get("draft_id") or "Unknown"

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("Draft sent successfully\n\n", style="green")

        # Draft ID
        content.append("Draft ID: ", style="dim")
        content.append(f"{draft_id}\n", style="")

        # Message ID
        content.append("Message ID: ", style="dim")
        content.append(f"{email_id}\n", style="")

        # Display in a panel with green border
        self.console.print(
            Panel(
                content,
                title="[bold white]✓ Draft Sent[/bold white]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _format_list_drafts(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format list_drafts tool results with draft list display."""
        draft_ids = result.get("draft_ids") or []
        total_count = result.get("total_count") or len(draft_ids)

        # Create the main content
        content = Text()

        # Header
        content.append("📝 Draft Emails\n", style="bold cyan")
        content.append(f"\n{total_count} draft{'s' if total_count != 1 else ''} found\n\n", style="")

        # Display drafts
        if not draft_ids:
            content.append("No draft emails found.\n", style="dim italic")
        else:
            for idx, draft_id in enumerate(draft_ids):
                content.append(f"• Draft ID: {draft_id}\n", style="")

                # Add spacing between drafts (except last one)
                if idx < len(draft_ids) - 1:
                    content.append("\n")

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold cyan]📝 Draft Emails[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _format_trash_email(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format trash_email tool results with trash confirmation."""
        email_id = result.get("id") or "Unknown"

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold yellow")
        content.append("Email moved to trash\n\n", style="yellow")

        # Message ID
        content.append("Message ID: ", style="dim")
        content.append(f"{email_id}\n", style="")

        # Info note
        content.append("\n💡 ", style="bold")
        content.append("Email can be recovered from trash", style="dim")

        # Display in a panel with yellow border
        self.console.print(
            Panel(
                content,
                title="[bold white]🗑️  Email Trashed[/bold white]",
                title_align="left",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def _format_delete_email_permanently(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format delete_email_permanently tool results with permanent deletion confirmation."""
        email_id = result.get("id") or "Unknown"

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold red")
        content.append("Email permanently deleted\n\n", style="red")

        # Message ID
        content.append("Message ID: ", style="dim")
        content.append(f"{email_id}\n", style="")

        # Warning note
        content.append("\n⚠️  ", style="bold")
        content.append("This action cannot be undone", style="dim red")

        # Display in a panel with red border
        self.console.print(
            Panel(
                content,
                title="[bold white]🗑️  Email Deleted Permanently[/bold white]",
                title_align="left",
                border_style="red",
                padding=(1, 2),
            )
        )

    def _format_modify_labels(self, tool: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Format modify_labels tool results with label modification confirmation."""
        email_id = result.get("id") or "Unknown"
        add_labels = result.get("add_labels") or []
        remove_labels = result.get("remove_labels") or []

        # Create the main content
        content = Text()

        # Success message
        content.append("✓ ", style="bold green")
        content.append("Labels modified successfully\n\n", style="green")

        # Message ID
        content.append("Message ID: ", style="dim")
        content.append(f"{email_id}\n\n", style="")

        # Added labels
        if add_labels:
            content.append("➕ Added labels:\n", style="bold green")
            for label in add_labels:
                content.append(f"  • {label}\n", style="green")
            if remove_labels:
                content.append("\n")

        # Removed labels
        if remove_labels:
            content.append("➖ Removed labels:\n", style="bold red")
            for label in remove_labels:
                content.append(f"  • {label}\n", style="red")

        # Display in a panel with cyan border
        self.console.print(
            Panel(
                content,
                title="[bold white]🏷️  Labels Modified[/bold white]",
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _format_generic(self, tool: Dict[str, Any], result: Any) -> None:
        """
        Generic formatter for tool results.
        Falls back to pretty-printed JSON with Rich styling.
        """
        tool_name = tool.get("tool_name") or tool.get("name") or "Unknown"

        # Convert result to JSON string
        json_str = json.dumps(result, indent=2, ensure_ascii=False)

        # Syntax highlight the JSON
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)

        # Display in a panel
        self.console.print(Panel(syntax, title=f"[bold cyan]{tool_name}[/bold cyan] result", border_style="blue"))
