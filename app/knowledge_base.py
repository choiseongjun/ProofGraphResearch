"""Optional internal PostgreSQL evidence source used alongside web search."""
from sqlalchemy import or_, select
from app.config import get_settings
from app.store import knowledge_documents, metadata
from sqlalchemy import create_engine


def search_internal_knowledge(query: str, limit: int = 4) -> list[dict[str, str]]:
    """Search user-managed `knowledge_documents` rows; an empty table is valid."""
    terms = [term for term in query.split() if len(term) > 1][:3]
    if not terms:
        return []
    try:
        engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        metadata.create_all(engine, tables=[knowledge_documents])
        predicates = [
            condition
            for term in terms
            for condition in (knowledge_documents.c.title.ilike(f"%{term}%"), knowledge_documents.c.content.ilike(f"%{term}%"))
        ]
        with engine.connect() as conn:
            rows = conn.execute(
                select(knowledge_documents.c.title, knowledge_documents.c.url, knowledge_documents.c.content)
                .where(or_(*predicates))
                .limit(limit)
            ).all()
        return [
            {"title": f"[내부 DB] {title}", "url": url or "", "content": content}
            for title, url, content in rows
        ]
    except Exception:
        # Internal evidence must not make a web-only research job fail.
        return []
