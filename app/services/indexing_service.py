import os
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any
import mimetypes
import shutil
import uuid

import graphrag.api as api
from graphrag.config.load_config import load_config
from graphrag.config.enums import IndexingMethod
from graphrag.logger.rich_progress import RichProgressLogger
from graphrag.index.typing.pipeline_run_result import PipelineRunResult

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(service="indexing")

# 支持的文档格式 → 文本提取器映射
_TEXT_EXTRACTORS: Dict[str, str] = {
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',  # .docx
    'application/msword': 'docx',                                                         # .doc（旧格式）
}

class IndexingService:
    def __init__(self):
        self.project_dir = settings.GRAPHRAG_PROJECT_DIR
        self.data_dir_name = settings.GRAPHRAG_DATA_DIR
        self.data_dir = os.path.join(self.project_dir, self.data_dir_name)
        
        # 默认配置文件
        self.default_config = 'settings.yaml'
        
        # 文件类型 → 配置文件映射（按需扩展，未匹配的类型走 default_config）
        self.config_mapping = {
            'application/pdf': 'settings.yaml',
        }
        
    def _get_file_type(self, file_path: str) -> str:
        """获取文件MIME类型"""
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'
    
    def _get_config_file(self, file_type: str) -> str:
        """根据文件类型获取对应的配置文件"""
        return self.config_mapping.get(file_type, self.default_config)
    
    def _check_existing_index(self, file_path: str, output_dir: str) -> bool:
        """检查文件是否已经建立索引"""
        file_name = Path(file_path).stem
        index_path = os.path.join(output_dir, f"{file_name}_index")
        return os.path.exists(index_path)
    
    def _prepare_user_directories(self, user_id: int) -> tuple:
        """为用户准备输入和输出目录"""
        # 生成用户UUID
        user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_{user_id}"))
        
        # 创建用户输入目录
        user_input_dir = os.path.join(self.data_dir, "input", user_uuid)
        os.makedirs(user_input_dir, exist_ok=True)
        
        # 创建用户输出目录
        user_output_dir = os.path.join(self.data_dir, "output", user_uuid)
        os.makedirs(user_output_dir, exist_ok=True)
        
        return user_input_dir, user_output_dir
    
    def _copy_file_to_input_dir(self, file_path: str, input_dir: str) -> str:
        """将文件复制到用户的输入目录"""
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(input_dir, file_name)
        
        # 复制文件
        shutil.copy2(file_path, dest_path)
        logger.info(f"已将文件复制到输入目录: {dest_path}")
        
        return dest_path
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """从 .docx 文件提取纯文本"""
        from docx import Document
        doc = Document(file_path)
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        # 也提取表格中的文本
        for table in doc.tables:
            for row in table.rows:
                row_texts = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        row_texts.append(cell_text)
                if row_texts:
                    paragraphs.append(' | '.join(row_texts))
        return '\n'.join(paragraphs)
    
    def _convert_to_text(self, file_path: str, file_type: str) -> str:
        """
        将非纯文本文件转换为 .txt 文件，返回转换后的 txt 文件路径。
        如果文件本身就是纯文本或不支持转换，返回原路径（由 GraphRAG settings.yaml 的 file_pattern 过滤处理）。
        """
        extractor = _TEXT_EXTRACTORS.get(file_type)
        if extractor is None:
            return file_path  # 不支持的格式，原样返回
        
        logger.info(f"正在将 {file_type} 文件转换为纯文本: {os.path.basename(file_path)}")
        
        if extractor == 'docx':
            text_content = self._extract_text_from_docx(file_path)
        else:
            return file_path
        
        if not text_content.strip():
            logger.warning(f"文件 {os.path.basename(file_path)} 提取的文本为空")
            return file_path
        
        # 写入同目录下的 .txt 文件
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_dir = os.path.dirname(file_path)
        txt_path = os.path.join(output_dir, f"{base_name}.txt")
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        logger.info(f"文本提取完成，已保存至: {txt_path} ({len(text_content)} 字符)")
        return txt_path
    
    async def process_file(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个文件的索引构建"""
        try:
            file_path = file_info['path']
            file_type = self._get_file_type(file_path)
            user_id = file_info.get('user_id', 0)  # 获取用户ID，默认为0
            
            logger.info(f"开始处理文件: {file_path}, 类型: {file_type}, 用户ID: {user_id}")
            
            # 非纯文本文件需要先提取文本，转换为 .txt
            file_to_index = self._convert_to_text(file_path, file_type)
            
            # 准备用户目录
            user_input_dir, user_output_dir = self._prepare_user_directories(user_id)
            
            # 清空输入目录中的旧文件（防止之前失败的 .docx/.pdf 等残留干扰）
            for old_file in os.listdir(user_input_dir):
                old_path = os.path.join(user_input_dir, old_file)
                if os.path.isfile(old_path):
                    os.remove(old_path)
                    logger.debug(f"已清理输入目录旧文件: {old_file}")
            
            # 复制文件到输入目录（复制的是 txt 而非原始二进制文件）
            input_file_path = self._copy_file_to_input_dir(file_to_index, user_input_dir)
            
            # 获取配置文件
            config_file = self._get_config_file(file_type)
            logger.info(f"使用配置文件: {config_file}")
            
            # 检查是否需要增量更新
            is_update = self._check_existing_index(input_file_path, user_output_dir)
            
            # 准备配置
            config_path = os.path.join(self.data_dir, config_file)
            if not os.path.exists(config_path):
                logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
                config_path = os.path.join(self.data_dir, self.default_config)
            
            # 设置配置覆盖
            # 注意：file_pattern 中的文件名需要转义正则特殊字符（如 .）
            safe_basename = re.escape(os.path.basename(input_file_path))
            config_overrides = {
                'input.base_dir': user_input_dir,
                'output.base_dir': user_output_dir,
                'input.file_pattern': f".*{safe_basename}$$"
            }
            
            # 加载配置
            graphrag_config = load_config(
                Path(self.data_dir),
                Path(config_path),
                config_overrides
            )
            
            # 创建进度记录器
            progress_logger = RichProgressLogger(prefix="graphrag-index")
            
            logger.info(f"开始{'增量更新' if is_update else '构建'}索引: {input_file_path}")
            logger.info(f"输入目录: {user_input_dir}")
            logger.info(f"输出目录: {user_output_dir}")
            
            # 执行索引构建
            index_result = await api.build_index(
                config=graphrag_config,
                method=IndexingMethod.Standard,
                is_update_run=is_update,
                memory_profile=False,
                progress_logger=progress_logger
            )
            
            # 处理结果
            result_info = {
                'original_file_path': file_path,
                'input_file_path': input_file_path,
                'file_type': file_type,
                'config_used': config_file,
                'is_update': is_update,
                'status': 'success',
                'user_id': user_id,
                'input_dir': user_input_dir,
                'output_dir': user_output_dir
            }
            
            # 检查是否有错误
            for workflow_result in index_result:
                if workflow_result.errors:
                    result_info['status'] = 'error'
                    result_info['errors'] = workflow_result.errors
                    logger.error(f"索引构建失败: {workflow_result.errors}")
            
            return result_info
            
        except Exception as e:
            logger.error(f"处理文件时发生错误: {str(e)}", exc_info=True)
            return {
                'file_path': file_path,
                'status': 'error',
                'error': str(e)
            }
    
    async def process_directory(self, directory_path: str, user_id: int = 0) -> Dict[str, Any]:
        """处理整个目录的索引构建"""
        try:
            results = []
            for root, _, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_info = {
                        'path': file_path,
                        'original_name': file,
                        'user_id': user_id
                    }
                    result = await self.process_file(file_info)
                    results.append(result)
            
            return {
                'status': 'success',
                'processed_files': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"处理目录时发生错误: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }