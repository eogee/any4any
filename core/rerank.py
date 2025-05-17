from fastapi import Header, HTTPException
from core.api_models import QADocs
from core.auth import verify_token
from core.models import ModelManager
import logging

logger = logging.getLogger(__name__)

async def rerank_documents(
    docs: QADocs,
    authorization: str = Header(None)
):
    """根据请求内容重排序文档"""
    await verify_token(authorization)
    
    try:
        if docs is None or len(docs.documents) == 0:
            return {"results": []}

        reranker = ModelManager.get_reranker()
        pairs = [[docs.query, doc] for doc in docs.documents]
        scores = reranker.compute_score(pairs, normalize=True)
        
        if isinstance(scores, float):
            scores = [scores]
            
        results = []
        for index, score in enumerate(scores):
            results.append({
                "index": index,
                "relevance_score": score,
                "text": docs.documents[index]
            })
        
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Reranking failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Reranking failed")
