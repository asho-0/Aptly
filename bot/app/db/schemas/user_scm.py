from pydantic import BaseModel


class UserProfileSchema(BaseModel):
    salutation: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    street: str = ""
    house_number: str = ""
    zip_code: str = ""
    city: str = ""
    persons_total: int | None = None
    wbs_available: bool = False
    wbs_date: str = ""
    wbs_rooms: int | None = None
    wbs_income: int | None = None
