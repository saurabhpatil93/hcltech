import hashlib
import json
import os
import re
from pathlib import Path

import requests
import streamlit as st

API = os.getenv('API_URL', 'http://localhost:8000')
st.set_page_config(page_title='Retail Assist Admin', page_icon='🔐', layout='wide')
st.title('🔐 Admin console')
st.caption('Restricted tools for managing policy documents.')
st.info('Indexed documents are stored in the persistent vector database. Uploads still being staged are kept in this browser session when you switch pages.')


def admin_headers():
    return {'X-Admin-Password': st.session_state['admin_password']}


if 'admin_password' not in st.session_state:
    with st.form('admin_login'):
        password = st.text_input('Admin password', type='password')
        submitted = st.form_submit_button('Sign in')
    if submitted:
        try:
            response = requests.get(
                f'{API}/admin/session',
                headers={'X-Admin-Password': password},
                timeout=10,
            )
            response.raise_for_status()
            st.session_state['admin_password'] = password
            st.rerun()
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            st.error(f'Admin sign-in failed: {detail}')
        except requests.RequestException as exc:
            st.error(f'Could not reach the admin API: {exc}')
    st.stop()

with st.sidebar:
    if st.button('Sign out'):
        del st.session_state['admin_password']
        st.rerun()

if 'pending_policy_uploads' not in st.session_state:
    st.session_state['pending_policy_uploads'] = []


def stage_uploads():
    staged = {
        item['digest']: item
        for item in st.session_state['pending_policy_uploads']
    }
    for uploaded_file in st.session_state.get('policy_uploads_widget') or []:
        content = uploaded_file.getvalue()
        digest = hashlib.sha256(uploaded_file.name.encode() + content).hexdigest()
        base_id = re.sub(
            r'[^A-Za-z0-9._-]+', '-', Path(uploaded_file.name).stem
        ).strip('-.') or 'document'
        staged[digest] = {
            'name': uploaded_file.name,
            'content': content,
            'content_type': uploaded_file.type or 'application/octet-stream',
            'digest': digest,
            'doc_id': f'{base_id}-{digest[:8]}',
        }
    st.session_state['pending_policy_uploads'] = list(staged.values())


try:
    source_response = requests.get(f'{API}/sources', timeout=10)
    source_response.raise_for_status()
    registered_sources = source_response.json().get('sources', [])
    st.subheader('Indexed documents')
    if registered_sources:
        st.dataframe(
            [
                {
                    'Document ID': source['doc_id'],
                    'Filename': source['filename'],
                    'Effective from': source['effective_from'],
                    'Effective to': source['effective_to'] or 'No end date',
                    'Version': source['version'],
                }
                for source in registered_sources
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption('No documents have been indexed yet.')
    if registered_sources:
        source_by_id = {source['doc_id']: source for source in registered_sources}
        selected_doc_id = st.selectbox(
            'Document to delete',
            options=list(source_by_id),
            format_func=lambda doc_id: (
                f"{source_by_id[doc_id]['filename']} ({doc_id})"
            ),
        )
        st.warning(
            'Deleting a document also removes its stored file, vector chunks, '
            'and rules registered to that document.'
        )
        confirm_delete = st.checkbox(
            f"Confirm deletion of {selected_doc_id}",
            key=f'confirm_delete_{selected_doc_id}',
        )
        if st.button('Delete indexed document', disabled=not confirm_delete):
            try:
                delete_response = requests.delete(
                    f'{API}/sources/{selected_doc_id}',
                    headers=admin_headers(),
                    timeout=30,
                )
                delete_response.raise_for_status()
                deleted = delete_response.json()
                st.success(
                    f"Deleted {deleted['doc_id']}: {deleted['deleted_chunks']} "
                    f"vector chunks and {deleted['deleted_rules']} rules removed."
                )
                st.rerun()
            except requests.HTTPError as exc:
                detail = exc.response.text if exc.response is not None else str(exc)
                st.error(f'Document deletion failed: {detail}')
            except requests.RequestException as exc:
                st.error(f'Could not reach the deletion API: {exc}')
except requests.RequestException as exc:
    st.error(f'Could not load indexed documents: {exc}')

st.subheader('Upload policy documents')
st.file_uploader(
    'Select one or more PDF, DOCX, TXT, or MD files',
    type=['pdf', 'docx', 'txt', 'md'],
    accept_multiple_files=True,
    key='policy_uploads_widget',
    on_change=stage_uploads,
)

pending_uploads = st.session_state['pending_policy_uploads']
if pending_uploads:
    st.write(f"{len(pending_uploads)} document(s) staged for ingestion.")
    for index, item in enumerate(pending_uploads):
        columns = st.columns([4, 1])
        columns[0].write(item['name'])
        if columns[1].button('Remove', key=f"remove_staged_{item['digest']}"):
            st.session_state['pending_policy_uploads'].pop(index)
            st.rerun()

    st.caption('Each file needs its own document ID. The other metadata fields apply to this batch.')
    metadata_columns = st.columns(3)
    authority_level = metadata_columns[0].number_input(
        'Authority level (lower is higher)', min_value=1, max_value=5, value=1
    )
    effective_from = metadata_columns[1].date_input('Effective from')
    version = metadata_columns[2].text_input('Version', value='1.0')
    category = st.text_input('Category', value='GENERAL')
    scope_tiers = st.text_input('Customer tiers', value='ALL')
    synthetic = st.checkbox('Synthetic/demo document', value=True)
    metadata_entries = []
    seen_ids = set()
    seen_ids = set()
    for index, item in enumerate(pending_uploads):
        with st.expander(item['name'], expanded=False):
            doc_id = st.text_input(
                'Document ID',
                value=item['doc_id'],
                key=f"doc_id_{item['digest']}",
            ).strip()
        if doc_id in seen_ids:
            st.error(f'Document ID must be unique within this batch: {doc_id}')
        seen_ids.add(doc_id)
        metadata_entries.append({
            'doc_id': doc_id,
            'authority_level': int(authority_level),
            'effective_from': effective_from.isoformat(),
            'version': version,
            'category': category,
            'scope_tiers': scope_tiers,
            'synthetic': 'Y' if synthetic else 'N',
        })

    if st.button('Ingest selected documents'):
        if not all(entry['doc_id'] for entry in metadata_entries):
            st.error('Every staged document needs a document ID.')
        elif len({entry['doc_id'] for entry in metadata_entries}) != len(metadata_entries):
            st.error('Document IDs must be unique within this upload batch.')
        elif not version.strip() or not category.strip() or not scope_tiers.strip():
            st.error('Version, category, and customer tiers are required.')
        else:
            files = [
                ('files', (item['name'], item['content'], item['content_type']))
                for item in pending_uploads
            ]
            try:
                response = requests.post(
                    f'{API}/ingest/batch',
                    headers=admin_headers(),
                    files=files,
                    data={'metadata_json': json.dumps(metadata_entries)},
                    timeout=600,
                )
                response.raise_for_status()
                result = response.json()
                st.success(f"Indexed {result['succeeded']} document(s); {result['failed']} failed.")
                completed_ids = set()
                for document in result['results']:
                    if document['status'] == 'indexed':
                        st.success(f"{document['filename']}: indexed as {document['doc_id']}")
                        completed_ids.add(document['doc_id'])
                    else:
                        st.error(f"{document['filename']}: {document['error']}")
                if completed_ids:
                    st.session_state['pending_policy_uploads'] = [
                        item for item, metadata in zip(pending_uploads, metadata_entries)
                        if metadata['doc_id'] not in completed_ids
                    ]
                    st.rerun()
            except requests.HTTPError as exc:
                detail = exc.response.text if exc.response is not None else str(exc)
                st.error(f'Ingestion request failed: {detail}')
            except requests.RequestException as exc:
                st.error(f'Could not reach the ingestion API: {exc}')
