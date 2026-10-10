from app.schemas import AskRequest
def test_ask_schema():assert AskRequest(question='What is the return policy?').question
