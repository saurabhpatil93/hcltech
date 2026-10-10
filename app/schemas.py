from pydantic import BaseModel,Field
from typing import Optional,Literal
from datetime import date
class AskRequest(BaseModel): question:str=Field(min_length=2,max_length=3000); as_of_date:Optional[date]=None
class AskResponse(BaseModel): trace_id:str; answer:str; answer_type:Literal['retrieved','calculated','not_found','conflict','explanation']; citations:list[dict]=[]; tools_invoked:list[dict]=[]; as_of_date:str
class HealthResponse(BaseModel): status:str; sqlite:str; vector_store:str; llm:str
