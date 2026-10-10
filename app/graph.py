from typing import TypedDict, Optional
import re
from langgraph.graph import StateGraph, END
from app.services.retrieval import search
from app.services.policy import choose_precedence
from app.services.llm import generate
from app.tools.retail_tools import order_lookup, check_return_eligibility, calculate_refund, check_warranty


class State(TypedDict, total=False):
    question: str
    customer_id: Optional[str]
    as_of_date: str
    tier: str
    hits: list
    chosen: list
    decisions: list
    conflict: bool
    tool_result: Optional[dict]
    answer: str
    answer_type: str


def retrieve(s):
    hits = search(s['question'], s['as_of_date'], tier=s.get('tier', 'STANDARD'))
    chosen, decisions, conflict = choose_precedence(hits, s['as_of_date'], tier=s.get('tier', 'STANDARD'))
    return {'hits': hits, 'chosen': chosen, 'decisions': decisions, 'conflict': conflict}


def tools(s):
    q = s['question'].lower()
    cid = s.get('customer_id')
    o = re.search(r'O-\d{6}', s['question'], re.I)
    k = re.search(r'SKU-[A-Z0-9-]+', s['question'], re.I)
    result = None
    if cid and o:
        oid = o.group().upper()
        if k and 'warranty' in q:
            result = check_warranty(cid, oid, k.group().upper(), s['as_of_date'])
        elif k and ('refund' in q or 'how much' in q):
            result = calculate_refund(cid, oid, k.group().upper(), s['as_of_date'])
        elif k and any(x in q for x in ('return', 'eligible')):
            result = check_return_eligibility(cid, oid, k.group().upper(), s['as_of_date'])
        elif any(x in q for x in ('order', 'where is', 'track', 'status')):
            result = order_lookup(cid, oid)
    return {'tool_result': result}


def answer(s):
    if s.get('conflict'):
        return {'answer': 'I found conflicting authorised sources that could not be resolved. Please contact support. Sources: ' +
                ', '.join(sorted({h['metadata'].get('doc_id', 'unknown') for h in s.get('chosen', [])})),
                'answer_type': 'conflict'}
    if not s.get('chosen') and not s.get('tool_result'):
        return {'answer': 'I could not find this information in the authorised sources.', 'answer_type': 'not_found'}
    ctx = '\n\n'.join(f"[{h['metadata'].get('doc_id')} | {h['metadata'].get('section')} | v{h['metadata'].get('version')} | effective {h['metadata'].get('effective_from')}] {h['text']}"
                      for h in s.get('chosen', []))
    try:
        a = generate(s['question'], ctx, s.get('tool_result'))
    except Exception as e:
        a = f'Local Ollama is unavailable. Start Ollama and pull the configured model. Error: {type(e).__name__}.'
    typ = 'calculated' if s.get('tool_result') and s['tool_result'].get('status') in ('calculated', 'eligible', 'ineligible', 'valid', 'expired_or_none') else ('retrieved' if s.get('chosen') else 'not_found')
    return {'answer': a, 'answer_type': typ}


g = StateGraph(State)
g.add_node('retrieve', retrieve)
g.add_node('tools', tools)
g.add_node('answer', answer)
g.set_entry_point('retrieve')
g.add_edge('retrieve', 'tools')
g.add_edge('tools', 'answer')
g.add_edge('answer', END)
assistant_graph = g.compile()