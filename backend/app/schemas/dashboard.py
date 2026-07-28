from pydantic import BaseModel


class SystemMetrics(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float
    redis_ok: bool
    postgres_ok: bool


class ProxyMetrics(BaseModel):
    total: int
    active: int
    inactive: int
    blocked: int
    testing: int


class GatewayMetrics(BaseModel):
    requests_total: int
    bytes_in_mb: float
    bytes_out_mb: float
    bytes_total_mb: float


class DashboardOut(BaseModel):
    system: SystemMetrics
    proxies: ProxyMetrics
    gateway: GatewayMetrics
