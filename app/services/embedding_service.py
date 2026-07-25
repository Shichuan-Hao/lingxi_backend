"""
文档向量化与 FAISS 索引服务。

使用 sentence-transformers 将文档分块向量化，
通过 FAISS 构建向量索引，支持相似度搜索和多格式文件（PDF/Word/TXT/Markdown）。
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import faiss
import numpy as np
import PyPDF2
from docx import Document
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logger import get_logger

# 国内镜像加速下载
if settings.HF_ENDPOINT:
    os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT

logger = get_logger(service="embedding")


class EmbeddingService:
    def __init__(self):
        # 使用多语言模型以支持中文；延迟加载避免启动时就阻塞
        self._model: Optional[SentenceTransformer] = None
        self.index_dir = Path("indexes")
        self.index_dir.mkdir(exist_ok=True)

        # 初始化空索引和文档存储
        self.dimension = 384  # 与模型输出维度一致
        self.current_index = None
        self.current_documents = {}

    @property
    def model(self) -> SentenceTransformer:
        """懒加载模型，并加锁避免并发重复加载"""
        if self._model is None:
            logger.info("\u23f3 加载 Embedding 模型，请稍候...")
            self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            logger.info("\u2705 Embedding 模型加载完成")
        return self._model

    def _get_index_path(self, file_id: str) -> str:
        """生成索引文件路径"""
        return f"index_{file_id}.bin"

    def _read_file(self, file_path: str) -> List[str]:
        """根据文件扩展名读取文本块"""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            chunks = []
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        chunks.append(text)
            return chunks

        if ext in (".doc", ".docx"):
            doc = Document(file_path)
            chunks = [para.text for para in doc.paragraphs if para.text.strip()]
            return chunks

        # 默认当纯文本处理
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return [text] if text.strip() else []

    async def create_embeddings(self, file_path: str, index_dir: str) -> Dict:
        """从文件创建向量索引"""
        logger.info(f"\U0001f4e5 开始向量化: {file_path}")

        try:
            # 在线程池中读取文件，避免阻塞事件循环
            text_chunks = await asyncio.to_thread(self._read_file, file_path)
            if not text_chunks:
                raise ValueError("未能从文件中提取到文本内容")

            logger.info(f"\U0001f4c4 提取 {len(text_chunks)} 个文本块")

            # 在线程池中执行 CPU 密集型向量化
            vectors = await asyncio.to_thread(self.model.encode, text_chunks)
            vectors = vectors.astype("float32")

            # 创建并添加向量
            index = faiss.IndexFlatL2(self.dimension)
            index.add(vectors)

            # 生成文件 ID
            file_hash = hashlib.md5(file_path.encode()).hexdigest()
            index_id = f"index_{file_hash}"

            # 创建文档数据
            documents = {}
            for i, text in enumerate(text_chunks):
                documents[str(i)] = {
                    "text": text,
                    "metadata": {
                        "page": i + 1,
                        "source": file_path,
                    },
                }

            # 在线程池中保存索引和文档数据
            await asyncio.to_thread(self._save_index, file_hash, index, documents)

            logger.info(f"\u2705 向量索引创建完成: {index_id}, {len(text_chunks)} 块")
            return {
                "status": "success",
                "index_id": index_id,
                "chunks": len(text_chunks),
            }

        except Exception as e:
            logger.error(f"\u274c 向量化失败: {str(e)}", exc_info=True)
            raise Exception(f"创建向量失败: {str(e)}")

    def _save_index(self, file_id: str, index: faiss.Index, documents: dict):
        """保存索引和文档数据"""
        index_path = self.index_dir / f"index_{file_id}.bin"
        docs_path = self.index_dir / f"docs_{file_id}.json"

        faiss.write_index(index, str(index_path))

        with open(docs_path, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)

    def _load_index(self, index_id: str):
        """加载索引和文档数据"""
        try:
            # 兼容旧格式
            index_path = self.index_dir / f"{index_id}.bin"
            docs_path = self.index_dir / f"docs_{index_id.replace('index_', '')}.json"

            if not index_path.exists() or not docs_path.exists():
                old_index_path = self.index_dir / f"index_{index_id}.bin"
                old_docs_path = self.index_dir / f"docs_{index_id}.json"

                if old_index_path.exists() and old_docs_path.exists():
                    index_path = old_index_path
                    docs_path = old_docs_path
                else:
                    raise FileNotFoundError(f"找不到索引文件: {index_id}")

            self.current_index = faiss.read_index(str(index_path))

            if self.current_index.d != self.dimension:
                raise ValueError(f"索引维度不匹配: 期望 {self.dimension}, 实际 {self.current_index.d}")

            with open(docs_path, "r", encoding="utf-8") as f:
                self.current_documents = json.load(f)

            if not self.current_documents:
                raise ValueError("文档数据为空")

            logger.info(
                f"\U0001f4e6 已加载索引 {index_id}: {self.current_index.ntotal} 向量, "
                f"{len(self.current_documents)} 文档"
            )

        except Exception as e:
            self.current_index = None
            self.current_documents = {}
            raise Exception(f"加载索引失败: {str(e)}")

    async def search(self, query: str, top_k: int = 3) -> List[dict]:
        """搜索最相关的文档片段"""
        try:
            if not self.current_index:
                raise Exception("未加载索引")

            query_vector = await asyncio.to_thread(self.model.encode, [query], False)
            query_vector = query_vector.astype("float32")

            distances, indices = self.current_index.search(query_vector, top_k)

            results = []
            for i in range(len(indices[0])):
                idx_str = str(int(indices[0][i]))
                if idx_str in self.current_documents:
                    results.append({
                        "score": float(distances[0][i]),
                        "content": self.current_documents[idx_str]["text"],
                        "metadata": self.current_documents[idx_str]["metadata"],
                    })

            return results

        except Exception as e:
            raise Exception(f"搜索失败: {str(e)}")
