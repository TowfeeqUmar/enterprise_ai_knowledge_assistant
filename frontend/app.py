import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
st.set_page_config(page_title="Enterprise AI Knowledge Assistant",
                   page_icon="📚", layout="wide")
st.title("📚 Enterprise AI Knowledge Assistant")
st.caption("Ask questions across your company's documents. Answers are grounded in retrieved sources.")

def api_error(response):
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text
    st.error(f"API error ({response.status_code}): {detail}")

with st.sidebar:
    st.header("Upload documents")
    uploaded = st.file_uploader(
        "Choose PDF, DOCX, CSV or TXT files",
        type=["pdf", "docx", "csv", "txt"],
        accept_multiple_files=True
    )
    if st.button("Upload and index", use_container_width=True, disabled=not uploaded):
        progress = st.empty()
        for item in uploaded:
            progress.info(f"Indexing {item.name}...")
            try:
                response = requests.post(
                    f"{API_URL}/upload",
                    files={"file": (item.name, item.getvalue(), item.type or "application/octet-stream")},
                    timeout=300
                )
                if response.ok:
                    st.success(f"{item.name}: {response.json().get('total_chunks')} chunks indexed.")
                else:
                    api_error(response)
            except requests.RequestException as exc:
                st.error(f"Could not connect to API: {exc}")
        progress.empty()

    st.divider()
    st.subheader("Knowledge base")
    try:
        docs_response = requests.get(f"{API_URL}/documents", timeout=15)
        docs_response.raise_for_status()
        docs = docs_response.json().get("documents", [])
        if not docs:
            st.info("No documents uploaded yet.")
        for doc in docs:
            with st.container(border=True):
                st.write(f"**{doc['filename']}**")
                st.caption(f"{doc['total_chunks']} chunks · {doc['file_type'].upper()} · {doc['size_bytes']:,} bytes")
                if st.button("Delete", key=f"delete_{doc['filename']}"):
                    deleted = requests.delete(
                        f"{API_URL}/documents/{requests.utils.quote(doc['filename'], safe='')}",
                        timeout=30
                    )
                    if deleted.ok:
                        st.success("Document deleted.")
                        st.rerun()
                    else:
                        api_error(deleted)
    except requests.RequestException as exc:
        st.warning(f"Backend unavailable: {exc}")

tab_chat, tab_history = st.tabs(["Ask documents", "Conversation history"])

with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("Sources used"):
                    for i, source in enumerate(message["sources"], start=1):
                        location = (f"page {source['page']}" if source.get("page")
                                    else f"row {source['row_start']}" if source.get("row_start")
                                    else "page unavailable")
                        st.markdown(
                            f"**Source {i}: {source.get('filename')}** — {location} "
                            f"(similarity: {source.get('similarity')})"
                        )
                        st.caption(source.get("excerpt", ""))
    question = st.chat_input("Ask a question about your company documents...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching documents and generating an answer..."):
                try:
                    response = requests.post(
                        f"{API_URL}/ask",
                        json={"question": question, "top_k": 5},
                        timeout=120
                    )
                    if response.ok:
                        result = response.json()
                        st.markdown(result["answer"])
                        if result.get("sources"):
                            with st.expander("Sources used", expanded=True):
                                for i, source in enumerate(result["sources"], start=1):
                                    location = (f"page {source['page']}" if source.get("page")
                                                else f"row {source['row_start']}" if source.get("row_start")
                                                else "page unavailable")
                                    st.markdown(
                                        f"**Source {i}: {source.get('filename')}** — {location} "
                                        f"(similarity: {source.get('similarity')})"
                                    )
                                    st.caption(source.get("excerpt", ""))
                        st.session_state.messages.append({
                            "role": "assistant", "content": result["answer"],
                            "sources": result.get("sources", [])
                        })
                    else:
                        api_error(response)
                except requests.RequestException as exc:
                    st.error(f"Could not connect to backend: {exc}")

with tab_history:
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("Saved conversations")
    with col2:
        if st.button("Clear history"):
            try:
                response = requests.delete(f"{API_URL}/history", timeout=15)
                if response.ok:
                    st.success("History cleared.")
                    st.rerun()
                else:
                    api_error(response)
            except requests.RequestException as exc:
                st.error(str(exc))
    try:
        response = requests.get(f"{API_URL}/history?limit=100", timeout=15)
        response.raise_for_status()
        history = response.json().get("history", [])
        if not history:
            st.info("No saved questions yet.")
        for item in history:
            with st.expander(item["question"]):
                st.markdown(item["answer"])
                st.caption(item["created_at"])
                import json
                for source in json.loads(item.get("sources_json", "[]")):
                    st.caption(f"{source.get('filename')} · page {source.get('page') or 'N/A'}")
    except requests.RequestException as exc:
        st.warning(f"Could not load history: {exc}")
