# -*- coding: utf-8 -*-
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime
import uuid

def new_project_id() -> str:
    return uuid.uuid4().hex[:8]

@dataclass
class WalletExport:
    address: str
    private_key_base58_64: str
    private_key_json_64: List[int]
    public_key_hex: str
    private_key_hex_32: str

@dataclass
class TokenMetadata:
    name: str
    symbol: str
    description: str
    image_uri: Optional[str] = None
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    category: Optional[str] = "memecoin"
    tags: List[str] = field(default_factory=list)
    decimals: int = 9
    initial_supply: int = 1_000_000_000

@dataclass
class PumpFunConfig:
    initial_liquidity_sol: float = 0.5
    jito_tip_microlamports: int = 0
    bonding_curve: Optional[str] = "default"

@dataclass
class Project:
    project_id: str
    name: str
    slug: str
    created_at: str
    wallets: List[WalletExport] = field(default_factory=list)
    token: TokenMetadata = field(default_factory=lambda: TokenMetadata(
        name="MyMeme", symbol="MEME", description="Memecoin Solana"))
    pumpfun: PumpFunConfig = field(default_factory=PumpFunConfig)
    extras: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)
