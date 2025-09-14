# Overview

Rug API v3.6 is a Flask-based REST API for managing Solana wallet "factory" projects across multiple networks (devnet/testnet/mainnet). The system provides comprehensive wallet management, SOL transfers, token operations, and project organization capabilities. It features a modular architecture with clear separation between API endpoints, business logic, authentication, and data persistence.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Framework
- **Flask 3.0+** as the core web framework with Blueprint-based route organization
- **RESTful API design** with consistent JSON responses and HTTP status codes
- **Swagger/OpenAPI 3.0** documentation available at `/docs` endpoint
- **Environment-based configuration** supporting multi-cluster deployments

## Authentication & Authorization
- **API key-based authentication** via Authorization header (Bearer token)
- **Per-cluster API keys** supporting different keys for devnet/testnet/mainnet
- **Optional authentication** controlled by `REQUIRE_AUTH` environment variable
- **Middleware decorator pattern** for consistent auth enforcement across endpoints

## Data Storage & Persistence
- **File-based storage** using JSON files organized in project directories
- **Atomic write operations** for data consistency using temporary files
- **Project-wallet hierarchy** with each project containing multiple wallets
- **Backup and trash system** for safe data operations and recovery
- **Private key storage** in multiple formats (base58, JSON array, hex)

## Solana Blockchain Integration
- **Multi-network support** (devnet/testnet/mainnet-beta) with configurable RPC endpoints
- **Solana-py and Solders libraries** for transaction creation and signing
- **Real-time balance checking** via RPC calls with commitment levels
- **Airdrop functionality** for devnet testing with retry mechanisms
- **Transaction building** for SOL transfers with fee estimation

## API Architecture
- **Blueprint-based routing** organized by domain (projects, wallets, transfers, tokens, utils)
- **Consistent error handling** with structured JSON error responses
- **Query parameter support** for cluster selection and RPC overrides
- **Request/response validation** with proper HTTP status codes
- **CORS support** for cross-origin requests

## Project & Wallet Management
- **Hierarchical organization** with projects containing multiple wallets
- **Automatic wallet naming** (Wallet 1, Wallet 2, etc.) with unique addressing
- **Wallet generation** using cryptographically secure random key generation
- **Import/export capabilities** for project portability
- **Metadata persistence** including creation timestamps and project slugs

## Transfer & Transaction System
- **SOL transfer operations** between wallets with balance validation
- **Mixing strategies** (random/roundrobin) for wallet fund distribution
- **Consolidation features** for gathering funds into single wallets
- **Fee estimation and management** to prevent insufficient balance errors
- **Transaction confirmation polling** with configurable timeouts

## Token Management
- **Token metadata storage** with configurable properties (name, symbol, description)
- **SPL token support** with holdings tracking and balance queries
- **Pump.fun integration** preparation (API key required)
- **Token account discovery** for comprehensive portfolio tracking

# External Dependencies

## Solana Ecosystem
- **Solana RPC nodes** for blockchain interaction across multiple networks
- **solana-py library** (v0.34.2) for Python-Solana integration
- **solders library** (v0.21.0) for efficient cryptographic operations
- **Public RPC endpoints** (api.devnet.solana.com, api.mainnet-beta.solana.com)

## Cryptography & Security
- **PyNaCl** for Ed25519 key generation and signing operations
- **base58** library for Solana address encoding/decoding
- **Python secrets module** for cryptographically secure random generation

## Web Framework & HTTP
- **Flask** (v3.0+) as the core web framework
- **flask-cors** for cross-origin resource sharing
- **flask-swagger-ui** for interactive API documentation
- **httpx** for external HTTP requests (price feeds, external APIs)

## Data Processing & Utilities
- **python-slugify** for URL-safe project naming
- **python-dotenv** for environment variable management
- **rich** library for CLI formatting and terminal output
- **cachetools** for response caching mechanisms

## Optional Integrations
- **Pump.fun API** for token creation (requires API key)
- **CoinGecko API** for SOL price data
- **Jupiter API** for token swapping (future integration)
- **External RPC providers** (Ankr, QuickNode) as alternatives to public endpoints