from __future__ import annotations

import io
import pandas as pd
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.db.models import Ticket, Manager, BusinessUnit

def _read_csv(upload: UploadFile) -> pd.DataFrame:
    raw = upload.file.read()
    
    try:
        return pd.read_csv(io.BytesIO(raw))
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(raw), encoding="cp1251")

def ingest_csv_bundle(db: Session, tickets: UploadFile | None, managers: UploadFile | None, business_units: UploadFile | None):
    out = {"tickets": 0, "managers": 0, "business_units": 0}

    if business_units is not None:
        df = _read_csv(business_units).fillna("")
        db.query(BusinessUnit).delete()
        for _, r in df.iterrows():
            db.add(BusinessUnit(office=str(r.get("Офис", r.get("office", ""))).strip(),
                                address=str(r.get("Адрес", r.get("address", ""))).strip()))
        db.commit()
        out["business_units"] = len(df)

    if managers is not None:
        df = _read_csv(managers).fillna("")
        db.query(Manager).delete()

        for _, r in df.iterrows():
            skills_raw = str(r.get("Навыки", r.get("skills", "")) or "")
            skills_raw = skills_raw.replace("[", "").replace("]", "").replace(";", ",")
            skills_list = [s.strip().upper() for s in skills_raw.split(",") if s.strip()]
            skills_clean = ",".join(skills_list)

            db.add(Manager(
                full_name=str(r.get("ФИО", r.get("full_name", ""))).strip(),
                position=str(r.get("Должность ", r.get("Должность", r.get("position", "Spec")))).strip(),
                business_unit=str(r.get("Офис", r.get("Бизнес-единица", r.get("business_unit", "")))).strip(),
                current_load=int(r.get("Количество обращений в работе", r.get("Кол-во обращений в работе", r.get("current_load", 0))) or 0),
                skills=skills_clean,
            ))

        db.commit()
        out["managers"] = len(df)

    if tickets is not None:
        df = _read_csv(tickets).fillna("")
        db.query(Ticket).delete()
        for _, r in df.iterrows():
            db.add(Ticket(
                client_guid=str(r.get("GUID клиента", r.get("client_guid", ""))).strip(),
                segment=str(r.get("Сегмент клиента", r.get("Сегмент", r.get("segment", "Mass")))).strip(),
                description=str(r.get("Описание ", r.get("Описание", r.get("description", "")))).strip(),
                attachment=str(r.get("Вложения", r.get("attachment", ""))).strip(),
                country=str(r.get("Страна", r.get("country", ""))).strip(),
                region=str(r.get("Область", r.get("region", ""))).strip(),
                city=str(r.get("Населённый пункт", r.get("Населенный пункт", r.get("city", "")))).strip(),
                street=str(r.get("Улица", r.get("street", ""))).strip(),
                house=str(r.get("Дом", r.get("house", ""))).strip(),
            ))
        db.commit()
        out["tickets"] = len(df)

    return {"status": "ok", "ingested": out}
