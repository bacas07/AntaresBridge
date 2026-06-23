from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AppointmentSchema(BaseModel):
    id: str
    scheduled_date: Optional[datetime] = None
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    service_code: Optional[str] = None
    appointment_type: Optional[str] = None
    status: Optional[str] = None
    is_fulfilled: Optional[bool] = False
    is_facturable: Optional[bool] = False
    sede_id: Optional[str] = None
    sede_attention_id: Optional[str] = None
    copay_value: Optional[float] = None
    total_value: Optional[float] = None
    diagnosis_code: Optional[str] = None
    phone_contact: Optional[str] = None
    observations: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source: Optional[str] = "antares"


class DoctorSchema(BaseModel):
    id: str
    name: Optional[str] = None
    specialty_id: Optional[str] = None
    specialty_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    agenda_web: Optional[bool] = False


class PatientSchema(BaseModel):
    id: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    first_name: Optional[str] = None
    second_name: Optional[str] = None
    last_name1: Optional[str] = None
    last_name2: Optional[str] = None
    birth_date: Optional[datetime] = None
    sex: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zone: Optional[str] = None
    status: Optional[str] = "ACTIVO"


class SyncPushResult(BaseModel):
    ids: list[str]
    success: bool = True
