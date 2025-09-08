"""Módulo simple de métricas en memoria.

Uso:
  from app.metrics import metrics, incr
  incr('citas_creadas')
  metrics.snapshot() -> dict serializable

Diseñado para entorno local / debugging. No persistente.
"""
from __future__ import annotations
from time import time
from typing import Dict
import threading

class MetricsStore:
	def __init__(self):
		self._lock = threading.Lock()
		self._counters: Dict[str,int] = {}
		self._gauges: Dict[str,float] = {}
		self._starts: Dict[str,float] = {}
		self._created_at = time()

	def incr(self, name: str, value: int = 1):
		with self._lock:
			self._counters[name] = self._counters.get(name,0) + value

	def gauge(self, name: str, value: float):
		with self._lock:
			self._gauges[name] = value

	def start_timer(self, name: str):
		self._starts[name] = time()

	def end_timer(self, name: str):
		start = self._starts.pop(name, None)
		if start is not None:
			elapsed = time()-start
			self.incr(f"timer_count_{name}")
			with self._lock:
				prev = self._gauges.get(f"timer_avg_{name}")
				if prev is None:
					self._gauges[f"timer_avg_{name}"] = elapsed
				else:
					self._gauges[f"timer_avg_{name}"] = (prev*0.7)+(elapsed*0.3)

	def snapshot(self):
		with self._lock:
			return {
				'uptime_sec': time()-self._created_at,
				'counters': dict(self._counters),
				'gauges': dict(self._gauges)
			}

metrics = MetricsStore()

def incr(name: str, value: int = 1):
	metrics.incr(name, value)

__all__ = ["metrics","incr","MetricsStore"]
