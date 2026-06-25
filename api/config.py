"""
AlphaFold 3 推理服务 API 配置管理模块

使用 pydantic-settings 管理所有环境变量配置，支持 .env 文件和环境变量注入。
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，通过环境变量或 .env 文件注入。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    #  API 服务
    # ------------------------------------------------------------------ #
    API_HOST: str = Field(
        default="0.0.0.0",
        description="API 服务监听地址",
    )
    API_PORT: int = Field(
        default=8015,
        description="API 服务监听端口",
    )

    # ------------------------------------------------------------------ #
    #  数据库
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = Field(
        default="sqlite:///app/data/alphafold3.db",
        description="SQLite 数据库连接 URL",
    )

    # ------------------------------------------------------------------ #
    #  AlphaFold 目录
    # ------------------------------------------------------------------ #
    ALPHAFOLD_DIR: str = Field(
        default="/data2/ntt/lvyizhuo/alphafold3",
        description="AlphaFold 3 代码及数据根目录（宿主机路径）",
    )
    MODEL_DIR: str = Field(
        default="/root/models",
        description="模型权重文件目录（容器内路径）",
    )
    DB_DIR: str = Field(
        default="/root/public_databases",
        description="搜索数据库目录（容器内路径）",
    )

    # ------------------------------------------------------------------ #
    #  存储目录
    # ------------------------------------------------------------------ #
    STORAGE_PATH: str = Field(
        default="/app/storage",
        description="任务文件存储根目录（容器内路径）",
    )
    INPUT_DIR: str = Field(
        default="/app/storage/inputs",
        description="用户上传输入文件目录",
    )
    OUTPUT_DIR: str = Field(
        default="/app/storage/tasks",
        description="推理结果输出目录",
    )

    # ------------------------------------------------------------------ #
    #  数据保留
    # ------------------------------------------------------------------ #
    DATA_RETENTION_DAYS: int = Field(
        default=30,
        description="历史数据保留天数，超过该天数的任务自动清理",
    )

    # ------------------------------------------------------------------ #
    #  日志
    # ------------------------------------------------------------------ #
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志级别",
    )
    LOG_FILE: str = Field(
        default="/app/logs/app.log",
        description="日志文件路径",
    )

    # ------------------------------------------------------------------ #
    #  上传限制（来自 PRD 5.1）
    # ------------------------------------------------------------------ #
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10,
        description="单次上传文件大小上限（MB）",
    )

    # ------------------------------------------------------------------ #
    #  校验器
    # ------------------------------------------------------------------ #

    @field_validator("API_PORT")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"API_PORT 必须在 1-65535 之间，当前值: {v}")
        return v

    @field_validator("DATA_RETENTION_DAYS")
    @classmethod
    def validate_retention_days(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"DATA_RETENTION_DAYS 必须 >= 1，当前值: {v}")
        return v

    @field_validator("MAX_UPLOAD_SIZE_MB")
    @classmethod
    def validate_upload_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"MAX_UPLOAD_SIZE_MB 必须 >= 1，当前值: {v}")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("sqlite:"):
            raise ValueError(
                f"当前仅支持 sqlite 数据库，DATABASE_URL 须以 'sqlite:' 开头，当前值: {v}"
            )
        return v

    @model_validator(mode="after")
    def validate_directories(self) -> "Settings":
        """校验目录路径不为空字符串。"""
        for field_name in ("STORAGE_PATH", "INPUT_DIR", "OUTPUT_DIR", "MODEL_DIR"):
            value = getattr(self, field_name)
            if not value or not value.strip():
                raise ValueError(f"{field_name} 不能为空")
        return self

    # ------------------------------------------------------------------ #
    #  便捷属性
    # ------------------------------------------------------------------ #

    @property
    def storage_tasks_path(self) -> Path:
        """返回任务存储目录的 Path 对象。"""
        return Path(self.OUTPUT_DIR)

    @property
    def upload_size_bytes(self) -> int:
        """返回上传文件大小上限（字节）。"""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def db_path(self) -> str:
        """从 DATABASE_URL 中提取 SQLite 文件路径。"""
        # sqlite:///path/to/db.db -> /path/to/db.db
        return self.database_path

    @property
    def database_path(self) -> str:
        """从 DATABASE_URL 中提取 SQLite 文件路径。"""
        prefix = "sqlite:///"
        if self.DATABASE_URL.startswith(prefix):
            return self.DATABASE_URL[len(prefix):]
        return self.DATABASE_URL


# ------------------------------------------------------------------ #
#  全局单例
# ------------------------------------------------------------------ #
settings = Settings()
