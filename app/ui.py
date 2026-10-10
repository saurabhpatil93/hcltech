import os

import requests
import streamlit as st

API = os.getenv('API_URL', 'http://localhost:8000')
st.set_page_config(page_title='Retail Assist', page_icon='🛍️', layout='wide')
st.title('🛍️ Retail Assist')
st.caption('Customer support · Ask about policies, your orders, returns, and warranties.')

with st.sidebar:
    st.subheader('Your demo account')
    customer_id = st.text_input('Customer ID', value='C1001').strip()
    st.caption('Your customer ID scopes order, return, and warranty questions to your demo data.')
    as_of_date = st.date_input('As-of date')
    try:
        health = requests.get(f'{API}/health', timeout=4)
        health.raise_for_status()
        st.json(health.json())
    except requests.RequestException as exc:
        st.warning(f'API unavailable: {exc}')

with st.expander('Example questions'):
    for question in (
        'What is the return window for electronics?',
        'Where is my order O-100001?',
        'Can I return SKU-E001 from order O-100001?',
        'How much refund will I get for SKU-E005 from order O-100005?',
        'Is SKU-E001 from order O-100001 under warranty?',
    ):
        st.code(question)

if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'chat_customer_id' not in st.session_state:
    st.session_state['chat_customer_id'] = customer_id
elif st.session_state['chat_customer_id'] != customer_id:
    st.session_state['chat_history'] = []
    st.session_state['chat_customer_id'] = customer_id

if st.session_state['chat_history']:
    if st.button('Clear conversation'):
        st.session_state['chat_history'] = []
        st.rerun()

with st.container(height=600, border=True):
    for message in st.session_state['chat_history']:
        with st.chat_message(message['role']):
            st.write(message['content'])
            if message['role'] == 'assistant' and message.get('trace_id'):
                st.caption(f"{message['answer_type']} · trace {message['trace_id']}")
                with st.expander('Citations'):
                    st.json(message['citations'])
                with st.expander('Order lookup and calculations'):
                    tool_calls = message['tools_invoked']
                    if not tool_calls:
                        st.caption(
                            'No order-specific lookup or calculation was needed for this question.'
                        )
                    for tool_call in tool_calls:
                        st.markdown(
                            f"**{tool_call.get('tool', 'Retail tool')}** · "
                            f"{tool_call.get('status', 'completed')}"
                        )
                        output = tool_call.get('output')
                        if output:
                            st.json(output)
                        else:
                            st.caption('The tool did not return additional data.')

question = st.chat_input('Ask about a policy, order, return, or warranty', disabled=not customer_id)
if question:
    st.session_state['chat_history'].append({'role': 'user', 'content': question})
    try:
        response = requests.post(
            f'{API}/ask',
            headers={'X-Customer-Id': customer_id},
            json={'question': question, 'as_of_date': str(as_of_date)},
            timeout=180,
        )
        response.raise_for_status()
        answer = response.json()
        st.session_state['chat_history'].append({
            'role': 'assistant',
            'content': answer['answer'],
            'answer_type': answer['answer_type'],
            'trace_id': answer['trace_id'],
            'citations': answer['citations'],
            'tools_invoked': answer.get('tools_invoked') or [],
        })
    except requests.RequestException as exc:
        st.session_state['chat_history'].append({
            'role': 'assistant',
            'content': f'Could not reach the support API: {exc}',
        })
    except (KeyError, ValueError) as exc:
        st.session_state['chat_history'].append({
            'role': 'assistant',
            'content': f'The support API returned an invalid response: {exc}',
        })
    st.rerun()
