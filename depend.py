from dataclasses import dataclass, asdict
from collections import defaultdict
from datetime import datetime
from sre_parse import parse
from statistics import median
import asyncio
import random


# ============================================================
# 1. 数据模型
# ============================================================

@dataclass
class RawPacket:
    """解析后的 A/B 数据包"""
    packet_type: str
    device_mac: str | None
    sequence: int
    timestamp: int | None
    heart_rate: float | None = None
    spo2: float | None = None
    temperature: float | None = None


@dataclass
class HealthSample:
    """A+B 合并后的标准健康数据"""
    device_mac: str
    sequence: int
    timestamp: int
    heart_rate: float | None
    spo2: float | None
    temperature: float | None
    health_score: float = 0.0

    def model_dump(self):
        return asdict(self)


@dataclass
class IngestResponse:
    success: bool
    message: str
    device_mac: str


# ============================================================
# 2. 双数据包识别
# ============================================================

class PacketParser:

    @staticmethod
    def identify(raw_hex):
        """
        根据帧头识别数据包类型：
        AA01 -> A包
        AA02 -> B包
        """

        if not raw_hex or len(raw_hex) < 4:
            return "UNKNOWN"

        header = raw_hex[:4].upper()

        if header == "AA01":
            return "A"

        if header == "AA02":
            return "B"

        return "UNKNOWN"

    @staticmethod
    def parse(raw_hex, packet_type):
        """根据 A/B 类型解析不同字段"""

        try:
            data = bytes.fromhex(raw_hex)
        except ValueError:
            return None

        # ----------------------------------------------------
        # A包：
        # AA 01 LEN MAC(6) SEQ(2) TIME(4) HR
        # ----------------------------------------------------
        if packet_type == "A":

            if len(data) < 16:
                return None

            return RawPacket(
                packet_type="A",
                device_mac=data[3:9].hex(":"),
                sequence=int.from_bytes(
                    data[9:11], "big"
                ),
                timestamp=int.from_bytes(
                    data[11:15], "big"
                ),
                heart_rate=data[15]
            )

        # ----------------------------------------------------
        # B包：
        # AA 02 LEN SEQ(2) SPO2 TEMP(2)
        # ----------------------------------------------------
        if packet_type == "B":

            if len(data) < 8:
                return None

            return RawPacket(
                packet_type="B",
                device_mac=None,
                sequence=int.from_bytes(
                    data[3:5], "big"
                ),
                timestamp=None,
                spo2=data[5],
                temperature=int.from_bytes(
                    data[6:8], "big"
                ) / 100
            )

        return None


# ============================================================
# 3. A/B 数据包合并
# ============================================================

class PacketMerger:

    def __init__(self):
        self.buffer = {}

    def merge(self, packet):
        """
        根据 sequence 匹配 A/B 包。
        两个包都到达后，才生成完整健康数据。
        """

        if packet is None:
            return None

        sequence = packet.sequence

        if sequence not in self.buffer:
            self.buffer[sequence] = {}

        self.buffer[sequence][
            packet.packet_type
        ] = packet

        cache = self.buffer[sequence]

        # A、B 没有同时到达
        if "A" not in cache or "B" not in cache:
            return None

        a_packet = cache["A"]
        b_packet = cache["B"]

        # 合并 A/B 字段
        sample = HealthSample(
            device_mac=a_packet.device_mac,
            sequence=sequence,
            timestamp=a_packet.timestamp,
            heart_rate=a_packet.heart_rate,
            spo2=b_packet.spo2,
            temperature=b_packet.temperature
        )

        # 合并完成后释放缓存
        del self.buffer[sequence]

        return sample


# ============================================================
# 4. 字段标准化
# ============================================================

class FieldMapper:

    @staticmethod
    def to_health(sample):
        return sample


class UnitNormalizer:

    @staticmethod
    def normalize(sample):

        if sample.heart_rate is not None:
            sample.heart_rate = round(
                sample.heart_rate, 1
            )

        if sample.spo2 is not None:
            sample.spo2 = round(
                sample.spo2, 1
            )

        if sample.temperature is not None:
            sample.temperature = round(
                sample.temperature, 1
            )

        return sample


# ============================================================
# 5. 历史数据
# ============================================================

class HealthRepository:

    def __init__(self):
        self.storage = defaultdict(list)

    def latest(
        self,
        device_mac,
        window=10
    ):
        return self.storage[
            device_mac
        ][-window:]

    def persist_sample(self, sample):
        self.storage[
            sample.device_mac
        ].append(sample)


# ============================================================
# 6. 异常值处理
# ============================================================

class OutlierHandler:

    @staticmethod
    def process(sample, history):

        if not history:
            return sample

        heart_rates = [
            item.heart_rate
            for item in history
            if item.heart_rate is not None
        ]

        if (
            heart_rates
            and sample.heart_rate is not None
        ):

            reference = median(
                heart_rates
            )

            # 当前值偏离历史中位数过大
            if abs(
                sample.heart_rate - reference
            ) > 60:

                sample.heart_rate = reference

        return sample


# ============================================================
# 7. 缺失值处理
# ============================================================

class MissingValueHandler:

    @staticmethod
    def impute(sample, history):

        if not history:
            return sample

        latest = history[-1]

        if sample.heart_rate is None:
            sample.heart_rate = (
                latest.heart_rate
            )

        if sample.spo2 is None:
            sample.spo2 = latest.spo2

        if sample.temperature is None:
            sample.temperature = (
                latest.temperature
            )

        return sample


# ============================================================
# 8. 个体基线
# ============================================================

class BaselineTracker:

    def __init__(self):
        self.baselines = {}

    def observe(self, sample):

        mac = sample.device_mac

        if mac not in self.baselines:

            self.baselines[mac] = {
                "heart_rate":
                    sample.heart_rate,

                "spo2":
                    sample.spo2,

                "temperature":
                    sample.temperature
            }

        return self.baselines[mac]


# ============================================================
# 9. 健康评分
# ============================================================

class HealthScoreService:

    @staticmethod
    def score(sample, baseline):

        score = 100.0

        # 心率偏离
        if (
            sample.heart_rate is not None
            and baseline["heart_rate"] is not None
        ):

            score -= abs(
                sample.heart_rate
                - baseline["heart_rate"]
            ) * 0.2

        # 血氧下降
        if (
            sample.spo2 is not None
            and baseline["spo2"] is not None
        ):

            score -= max(
                0,
                baseline["spo2"]
                - sample.spo2
            ) * 2

        # 体温偏离
        if (
            sample.temperature is not None
            and baseline["temperature"] is not None
        ):

            score -= abs(
                sample.temperature
                - baseline["temperature"]
            ) * 5

        return round(
            max(0, min(100, score)),
            2
        )


# ============================================================
# 10. WebSocket 实时推送
# ============================================================

class WebSocketManager:

    @staticmethod
    async def broadcast(
        device_mac,
        data
    ):

        print(
            f"[实时推送] "
            f"设备={device_mac} | "
            f"HR={data['heart_rate']} | "
            f"SpO2={data['spo2']} | "
            f"Temp={data['temperature']} | "
            f"Score={data['health_score']}"
        )


# ============================================================
# 11. 全局服务对象
# ============================================================

parser = PacketParser()
merger = PacketMerger()

mapper = FieldMapper()
normalizer = UnitNormalizer()

health = HealthRepository()

outlier_handler = OutlierHandler()
miss_value = MissingValueHandler()

baseline_tracker = BaselineTracker()
health_score_service = HealthScoreService()

websocket = WebSocketManager()

# ============================================================
# 核心数据处理函数
# ============================================================
def ingest(hex):
    #数据识别与解析合并
    type = parser.identify(hex)
    pack = parser.parse(hex, type)
    com = merger.merge(pack)

    #数据处理
    sample = normalizer.normalize(com)
    history = health.latest(sample, 10)
    sample = miss_value.impute(history)

    #实时推送
    websocket.broadcast(sample)
    return IngestResponse(
        sample.device_mac
    )



    
    
    
    

    

    

    
    
def build_a_packet(
    mac,
    sequence,
    timestamp,
    heart_rate
):

    mac_bytes = bytes.fromhex(
        mac.replace(":", "")
    )

    packet = (
        b"\xAA\x01"
        + bytes([16])
        + mac_bytes
        + sequence.to_bytes(2, "big")
        + timestamp.to_bytes(4, "big")
        + bytes([heart_rate])
    )

    return packet.hex().upper()


# ============================================================
# 14. 模拟 B 包
# ============================================================

def build_b_packet(
    sequence,
    spo2,
    temperature
):

    temp = int(
        temperature * 100
    )

    packet = (
        b"\xAA\x02"
        + bytes([8])
        + sequence.to_bytes(2, "big")
        + bytes([spo2])
        + temp.to_bytes(2, "big")
    )

    return packet.hex().upper()


# ============================================================
# 15. 测试入口
# ============================================================

async def main():

    mac = "A4:C1:38:9F:22:08"

    timestamp = int(
        datetime.now().timestamp()
    )

    print(
        "\n========== 手环数据接入 ==========\n"
    )

    for sequence in range(1, 6):

        heart_rate = random.choice(
            [72, 75, 78, 80]
        )

        spo2 = random.choice(
            [96, 97, 98]
        )

        temperature = random.choice(
            [36.5, 36.6, 36.7]
        )

        # 生成 A 包
        packet_a = build_a_packet(
            mac,
            sequence,
            timestamp,
            heart_rate
        )

        # 生成 B 包
        packet_b = build_b_packet(
            sequence,
            spo2,
            temperature
        )

        print(
            f"[A包] {packet_a}"
        )

        result_a = (
            await process_wristband_data(
                packet_a
            )
        )

        print(
            f"      -> {result_a.message}"
        )

        print(
            f"[B包] {packet_b}"
        )

        result_b = (
            await process_wristband_data(
                packet_b
            )
        )

        print(
            f"      -> {result_b.message}"
        )


# ============================================================
# 16. 程序入口
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())