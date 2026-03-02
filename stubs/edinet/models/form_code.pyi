from _typeshed import Incomplete
from edinet.exceptions import EdinetWarning as EdinetWarning
from pydantic import BaseModel

class FormCodeEntry(BaseModel):
    """様式コードリストの1行。"""
    model_config: Incomplete
    ordinance_code: str
    form_code: str
    form_number: str
    form_name: str
    doc_type_name: str
    disclosure_type: str
    note: str | None

FORM_CODE_RECORD_COUNT: Incomplete

def get_form_code(ordinance_code: str, form_code: str) -> FormCodeEntry | None:
    """府令コードと様式コードのペアから FormCodeEntry を返す。"""
def all_form_codes() -> list[FormCodeEntry]:
    """全様式コードの一覧を返す。"""
