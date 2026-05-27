from ..models import Contact, ContactResult
from ..providers.contacts_base import ContactsProvider


class ContactsService:
    def __init__(self, provider: ContactsProvider):
        self.provider = provider

    def create(self, *, token: str, contact: Contact) -> ContactResult:
        return self.provider.create_contact(token=token, contact=contact)

    def update(self, *, token: str, resource_name: str, patch: dict) -> ContactResult:
        return self.provider.update_contact(token=token, resource_name=resource_name, patch=patch)

    def delete(self, *, token: str, resource_name: str) -> ContactResult:
        return self.provider.delete_contact(token=token, resource_name=resource_name)

    def list_contacts(self, *, token: str, page_size: int = 100) -> list[ContactResult]:
        return self.provider.list_contacts(token=token, page_size=page_size)

    def search_contacts(self, *, token: str, query: str, page_size: int = 100) -> list[ContactResult]:
        return self.provider.search(token=token, query=query, page_size=page_size)

    def list_other_contacts(self, *, token: str, page_size: int = 100) -> list[ContactResult]:
        return self.provider.list_other_contacts(token=token, page_size=page_size)
