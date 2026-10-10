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

question = st.chat_input('Ask about a policy, order, return, or warranty', disabled=not customer_id)
if question:
    with st.chat_message('user'):
        st.write(question)
    with st.chat_message('assistant'):
        try:
            response = requests.post(
                f'{API}/ask',
                headers={'X-Customer-Id': customer_id},
                json={'question': question, 'as_of_date': str(as_of_date)},
                timeout=180,
            )
            response.raise_for_status()
            answer = response.json()
            st.write(answer['answer'])
            st.caption(f"{answer['answer_type']} · trace {answer['trace_id']}")
            with st.expander('Citations'):
                st.json(answer['citations'])
            with st.expander('Order lookup and calculations'):
                tool_calls = answer.get('tools_invoked') or []
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
        except requests.RequestException as exc:
            st.error(f'Could not reach the support API: {exc}')
        except (KeyError, ValueError) as exc:
            st.error(f'The support API returned an invalid response: {exc}')
