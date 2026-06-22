
import json
import time
import asyncio
from typing import List, Dict, Callable, Optional, Type
from loguru import logger

try:
    from nostr_sdk import Keys, Client, EventBuilder, Tag, Filter, Kind
    NOSTR_SDK_AVAILABLE = True
except ImportError:
    NOSTR_SDK_AVAILABLE = False
    logger.warning("nostr-sdk 未安装，部分功能将不可用")

from nip304 import (
    NIP304Event,
    NIP304EventType,
    NIP304Factory,
    compute_event_id,
)


class NostrClient:

    def __init__(self, private_key: str = "", relay_urls: List[str] = None):
        if not NOSTR_SDK_AVAILABLE:
            raise ImportError("nostr-sdk 未安装，请运行 pip install nostr-sdk")

        if private_key:
            self.keys = Keys.parse(private_key)
        else:
            self.keys = Keys.generate()

        self.pubkey = self.keys.public_key().to_hex()
        self.pubkey_bech32 = self.keys.public_key().to_bech32()

        logger.info(f"Nostr 客户端初始化完成，公钥: {self.pubkey_bech32}")

        self.client = Client(self.keys)

        self.relay_urls = relay_urls or []
        self.connected = False

        self._event_callbacks: Dict[int, List[Callable]] = {}

    def add_relay(self, relay_url: str):
        self.relay_urls.append(relay_url)
        logger.info(f"添加中继: {relay_url}")

    def connect(self):
        for relay_url in self.relay_urls:
            try:
                self.client.add_relay(relay_url)
                logger.info(f"连接中继成功: {relay_url}")
            except Exception as e:
                logger.error(f"连接中继失败 {relay_url}: {e}")

        self.client.connect()
        self.connected = True
        logger.info("Nostr 客户端已连接到中继网络")

    def disconnect(self):
        if self.connected:
            self.client.disconnect()
            self.connected = False
            logger.info("Nostr 客户端已断开连接")

    def publish_event(self, event: NIP304Event) -> str:
        if not self.connected:
            raise RuntimeError("客户端未连接到中继")

        tags = [Tag.parse(tag) for tag in event.tags]

        event_builder = EventBuilder(
            kind=event.kind,
            content=event.content,
            tags=tags
        )

        nostr_event = event_builder.to_event(self.keys)
        event_id = nostr_event.id().to_hex()

        try:
            self.client.send_event(nostr_event)
            logger.info(f"事件发布成功: kind={event.kind}, id={event_id}")
            return event_id
        except Exception as e:
            logger.error(f"事件发布失败: {e}")
            raise

    def publish_asset_event(self, **kwargs) -> str:
        event = NIP304Factory.create_asset_publish(**kwargs)
        return self.publish_event(event)

    def publish_demand_event(self, **kwargs) -> str:
        event = NIP304Factory.create_demand_publish(**kwargs)
        return self.publish_event(event)

    def publish_compute_param_event(self, **kwargs) -> str:
        event = NIP304Factory.create_compute_param(**kwargs)
        return self.publish_event(event)

    def publish_trade_receipt_event(self, **kwargs) -> str:
        event = NIP304Factory.create_trade_receipt(**kwargs)
        return self.publish_event(event)

    def publish_reputation_event(self, **kwargs) -> str:
        event = NIP304Factory.create_reputation_rating(**kwargs)
        return self.publish_event(event)

    def subscribe_events(
        self,
        kinds: List[int] = None,
        authors: List[str] = None,
        tag_filters: Dict[str, str] = None,
        since: int = 0,
        until: int = 0,
        limit: int = 0,
        callback: Callable = None
    ) -> str:
        if not self.connected:
            raise RuntimeError("客户端未连接到中继")

        filter_builder = Filter()

        if kinds:
            filter_builder.kinds([Kind(k) for k in kinds])

        if authors:
            filter_builder.authors(authors)

        if tag_filters:
            for tag_name, tag_value in tag_filters.items():
                filter_builder.custom_tag(tag_name, [tag_value])

        if since > 0:
            filter_builder.since(since)

        if until > 0:
            filter_builder.until(until)

        if limit > 0:
            filter_builder.limit(limit)

        subscription_id = f"sub_{int(time.time())}"

        if callback:
            logger.info(f"订阅创建成功: {subscription_id}")

        return subscription_id

    def query_events(
        self,
        kinds: List[int] = None,
        authors: List[str] = None,
        tag_filters: Dict[str, str] = None,
        limit: int = 100
    ) -> List[NIP304Event]:
        if not self.connected:
            raise RuntimeError("客户端未连接到中继")

        filter_builder = Filter()

        if kinds:
            filter_builder.kinds([Kind(k) for k in kinds])

        if authors:
            filter_builder.authors(authors)

        if tag_filters:
            for tag_name, tag_value in tag_filters.items():
                filter_builder.custom_tag(tag_name, [tag_value])

        filter_builder.limit(limit)

        try:
            events = self.client.get_events_of([filter_builder])
            result = []

            for event in events:
                event_dict = {
                    "id": event.id().to_hex(),
                    "pubkey": event.pubkey().to_hex(),
                    "created_at": event.created_at().as_secs(),
                    "kind": event.kind().as_u64(),
                    "tags": [[tag.as_vec()[0], tag.as_vec()[1]] if len(tag.as_vec()) >= 2 else [tag.as_vec()[0]] for tag in event.tags()],
                    "content": event.content(),
                    "sig": event.signature().to_hex(),
                }
                result.append(NIP304Factory.parse_event(event_dict))

            logger.info(f"查询到 {len(result)} 个事件")
            return result

        except Exception as e:
            logger.error(f"查询事件失败: {e}")
            return []

    def query_assets(self, risk_type: str = "", limit: int = 50) -> List:
        tag_filters = {}
        if risk_type:
            tag_filters["risk_type"] = risk_type

        return self.query_events(
            kinds=[NIP304EventType.ASSET_PUBLISH.value],
            tag_filters=tag_filters if tag_filters else None,
            limit=limit
        )

    def query_demands(self, risk_type: str = "", limit: int = 50) -> List:
        tag_filters = {}
        if risk_type:
            tag_filters["risk_type"] = risk_type

        return self.query_events(
            kinds=[NIP304EventType.DEMAND_PUBLISH.value],
            tag_filters=tag_filters if tag_filters else None,
            limit=limit
        )

    def get_public_key(self, bech32: bool = True) -> str:
        if bech32:
            return self.pubkey_bech32
        return self.pubkey

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class MockNostrClient:

    def __init__(self, private_key: str = ""):
        import secrets

        if private_key:
            self.private_key = private_key
        else:
            self.private_key = secrets.token_hex(32)

        self.pubkey = hashlib.sha256(self.private_key.encode()).hexdigest()
        self.pubkey_bech32 = f"npub{self.pubkey[:10]}..."

        self._event_store: List[Dict] = []

        self._subscriptions: Dict[str, Callable] = {}

        logger.info(f"模拟 Nostr 客户端初始化完成，公钥: {self.pubkey_bech32}")
        self.connected = False

    def add_relay(self, relay_url: str):
        logger.info(f"[模拟] 添加中继: {relay_url}")

    def connect(self):
        self.connected = True
        logger.info("[模拟] Nostr 客户端已连接")

    def disconnect(self):
        self.connected = False
        logger.info("[模拟] Nostr 客户端已断开")

    def publish_event(self, event: NIP304Event) -> str:
        if not self.connected:
            raise RuntimeError("客户端未连接")

        event.pubkey = self.pubkey

        event_dict = event.to_dict()
        event_dict["pubkey"] = self.pubkey
        event_id = compute_event_id(event_dict)
        event.event_id = event_id

        event.sig = f"sig_{event_id[:16]}"

        self._event_store.append(event.to_dict())

        for sub_id, callback in self._subscriptions.items():
            try:
                callback(event)
            except Exception as e:
                logger.error(f"订阅回调执行失败 {sub_id}: {e}")

        logger.info(f"[模拟] 事件发布成功: kind={event.kind}, id={event_id}")
        return event_id

    def query_events(
        self,
        kinds: List[int] = None,
        authors: List[str] = None,
        tag_filters: Dict[str, str] = None,
        limit: int = 100
    ) -> List[NIP304Event]:
        if not self.connected:
            raise RuntimeError("客户端未连接")

        results = []

        for event_data in self._event_store:
            if kinds and event_data["kind"] not in kinds:
                continue

            if authors and event_data["pubkey"] not in authors:
                continue

            if tag_filters:
                match = True
                event_tags = {tag[0]: tag[1] for tag in event_data["tags"] if len(tag) >= 2}
                for tag_name, tag_value in tag_filters.items():
                    if event_tags.get(tag_name) != tag_value:
                        match = False
                        break
                if not match:
                    continue

            results.append(NIP304Factory.parse_event(event_data))

            if len(results) >= limit:
                break

        logger.info(f"[模拟] 查询到 {len(results)} 个事件")
        return results

    def subscribe_events(self, callback: Callable = None, **kwargs) -> str:
        import uuid
        sub_id = str(uuid.uuid4())

        if callback:
            self._subscriptions[sub_id] = callback

        logger.info(f"[模拟] 订阅创建成功: {sub_id}")
        return sub_id

    def get_public_key(self, bech32: bool = True) -> str:
        if bech32:
            return self.pubkey_bech32
        return self.pubkey

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


import hashlib


def create_nostr_client(
    private_key: str = "",
    relay_urls: List[str] = None,
    use_mock: bool = False
) -> NostrClient:
    if use_mock or not NOSTR_SDK_AVAILABLE:
        if not use_mock:
            logger.warning("nostr-sdk 不可用，使用模拟客户端")
        return MockNostrClient(private_key)
    else:
        return NostrClient(private_key, relay_urls)


__all__ = [
    "NostrClient",
    "MockNostrClient",
    "create_nostr_client",
]
