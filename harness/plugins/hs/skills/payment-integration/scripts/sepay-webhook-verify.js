#!/usr/bin/env node

/**
 * SePay Webhook Verification Script
 *
 * Verifies SePay webhook authenticity and processes transaction data.
 * Supports SePay's four webhook auth methods: HMAC-SHA256, API Key, OAuth2, none.
 *
 * Usage:
 *   node sepay-webhook-verify.js <webhook-payload-json>
 *
 * Environment Variables:
 *   SEPAY_WEBHOOK_AUTH_TYPE  - Authentication type (hmac, api_key, oauth2, none)
 *   SEPAY_WEBHOOK_API_KEY    - API key for verification (auth type api_key)
 *   SEPAY_WEBHOOK_SECRET     - Shared secret for HMAC-SHA256 (auth type hmac)
 *   SEPAY_WEBHOOK_SIGNATURE  - (CLI testing) X-SePay-Signature header value
 *   SEPAY_WEBHOOK_TIMESTAMP  - (CLI testing) X-SePay-Timestamp header value
 *
 * HMAC-SHA256 (SePay's recommended method, per developer.sepay.vn): SePay signs
 * "{timestamp}.{raw_body}" with the webhook Secret Key and sends
 *   X-SePay-Signature: sha256=<hex>
 *   X-SePay-Timestamp: <unix_seconds>
 * Verification MUST run over the RAW request body bytes — re-serializing parsed
 * JSON changes whitespace/ordering/escaping and breaks the signature.
 */

const crypto = require('crypto');

// ±5 minutes: SePay's documented replay window for the signed timestamp.
const HMAC_MAX_SKEW_SECONDS = 300;

/** Case-insensitive header lookup (HTTP header names are case-insensitive). */
function getHeader(headers, name) {
  if (!headers) return undefined;
  const want = name.toLowerCase();
  for (const key of Object.keys(headers)) {
    if (key.toLowerCase() === want) return headers[key];
  }
  return undefined;
}

/** Constant-time string compare that never throws on length mismatch. */
function safeEqual(a, b) {
  const ba = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

class SePayWebhookVerifier {
  constructor(authType = 'none', apiKey = null, secret = null) {
    this.authType = authType;
    this.apiKey = apiKey;
    this.secret = secret;
  }

  /**
   * Verify webhook authenticity.
   * @param {object} headers - request headers
   * @param {string} [rawBody] - the RAW request body, required for hmac
   */
  verifyAuthentication(headers, rawBody) {
    if (this.authType === 'none') {
      console.log('⚠️  Warning: No authentication configured');
      return true;
    }

    if (this.authType === 'hmac') {
      return this.verifyHmac(headers, rawBody);
    }

    if (this.authType === 'api_key') {
      const authHeader = getHeader(headers, 'authorization');

      if (!authHeader) {
        throw new Error('Missing Authorization header');
      }

      const expectedAuth = `Apikey ${this.apiKey}`;
      // Constant-time compare so a wrong key cannot be guessed by timing.
      if (!safeEqual(authHeader, expectedAuth)) {
        throw new Error('Invalid API key');
      }

      return true;
    }

    if (this.authType === 'oauth2') {
      const authHeader = getHeader(headers, 'authorization');

      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        throw new Error('Missing or invalid OAuth2 Bearer token');
      }

      // In production, verify token with OAuth2 provider
      console.log('✓ OAuth2 token present (full verification needed in production)');
      return true;
    }

    throw new Error(`Unknown auth type: ${this.authType}`);
  }

  /**
   * Verify SePay's HMAC-SHA256 signature over "{timestamp}.{rawBody}".
   * Rejects a missing/expired timestamp (replay protection) and any signature
   * mismatch, using a constant-time comparison.
   */
  verifyHmac(headers, rawBody) {
    if (!this.secret) {
      throw new Error('SEPAY_WEBHOOK_SECRET not configured for hmac auth');
    }
    if (rawBody == null) {
      throw new Error('Raw request body required for HMAC verification');
    }

    const signature = getHeader(headers, 'x-sepay-signature');
    const timestamp = getHeader(headers, 'x-sepay-timestamp');
    if (!signature || !timestamp) {
      throw new Error('Missing X-SePay-Signature or X-SePay-Timestamp header');
    }

    // Replay protection: reject timestamps outside the ±5min window.
    const ts = parseInt(timestamp, 10);
    const now = Math.floor(Date.now() / 1000);
    if (!Number.isFinite(ts) || Math.abs(now - ts) > HMAC_MAX_SKEW_SECONDS) {
      throw new Error('Webhook timestamp expired or invalid (possible replay)');
    }

    const expected =
      'sha256=' +
      crypto.createHmac('sha256', this.secret)
        .update(`${timestamp}.${rawBody}`)
        .digest('hex');

    if (!safeEqual(signature, expected)) {
      throw new Error('Invalid HMAC signature');
    }

    return true;
  }

  /**
   * Check for duplicate transactions
   */
  isDuplicate(transactionId, processedIds = new Set()) {
    return processedIds.has(transactionId);
  }

  /**
   * Validate webhook payload structure
   */
  validatePayload(payload) {
    const required = [
      'id',
      'gateway',
      'transactionDate',
      'accountNumber',
      'transferType',
      'transferAmount',
      'referenceCode'
    ];

    for (const field of required) {
      if (!(field in payload)) {
        throw new Error(`Missing required field: ${field}`);
      }
    }

    // Validate transfer type
    if (!['in', 'out'].includes(payload.transferType)) {
      throw new Error(`Invalid transferType: ${payload.transferType}`);
    }

    // Validate amount
    if (typeof payload.transferAmount !== 'number' || payload.transferAmount <= 0) {
      throw new Error('Invalid transferAmount');
    }

    return true;
  }

  /**
   * Process webhook payload
   */
  process(payload, headers = {}, rawBody = null) {
    try {
      // 1. Verify authentication (HMAC needs the raw body bytes)
      this.verifyAuthentication(headers, rawBody);

      // 2. Validate payload structure
      this.validatePayload(payload);

      // 3. Extract transaction data
      const transaction = {
        id: payload.id,
        gateway: payload.gateway,
        transactionDate: new Date(payload.transactionDate),
        accountNumber: payload.accountNumber,
        code: payload.code || null,
        content: payload.content || '',
        transferType: payload.transferType,
        transferAmount: payload.transferAmount,
        accumulated: payload.accumulated || 0,
        subAccount: payload.subAccount || null,
        referenceCode: payload.referenceCode
      };

      return {
        success: true,
        transaction,
        isIncoming: transaction.transferType === 'in',
        isOutgoing: transaction.transferType === 'out'
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }
}

// CLI Usage
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log('Usage: node sepay-webhook-verify.js <webhook-payload-json>');
    console.log('\nEnvironment Variables:');
    console.log('  SEPAY_WEBHOOK_AUTH_TYPE - Authentication type (hmac, api_key, oauth2, none)');
    console.log('  SEPAY_WEBHOOK_API_KEY   - API key for verification (api_key)');
    console.log('  SEPAY_WEBHOOK_SECRET    - Shared secret (hmac)');
    console.log('  SEPAY_WEBHOOK_SIGNATURE / SEPAY_WEBHOOK_TIMESTAMP - headers for hmac testing');
    process.exit(1);
  }

  try {
    // args[0] is the RAW body string: parse for the payload but keep the exact
    // bytes for HMAC (re-serializing parsed JSON would break the signature).
    const rawBody = args[0];
    const payload = JSON.parse(rawBody);
    const authType = process.env.SEPAY_WEBHOOK_AUTH_TYPE || 'none';
    const apiKey = process.env.SEPAY_WEBHOOK_API_KEY || null;
    const secret = process.env.SEPAY_WEBHOOK_SECRET || null;

    const verifier = new SePayWebhookVerifier(authType, apiKey, secret);

    // Mock headers for CLI testing
    const headers = {};
    if (authType === 'api_key' && apiKey) {
      headers['Authorization'] = `Apikey ${apiKey}`;
    }
    if (authType === 'hmac') {
      if (process.env.SEPAY_WEBHOOK_SIGNATURE) {
        headers['X-SePay-Signature'] = process.env.SEPAY_WEBHOOK_SIGNATURE;
      }
      if (process.env.SEPAY_WEBHOOK_TIMESTAMP) {
        headers['X-SePay-Timestamp'] = process.env.SEPAY_WEBHOOK_TIMESTAMP;
      }
    }

    const result = verifier.process(payload, headers, rawBody);

    if (result.success) {
      console.log('✓ Webhook verified successfully\n');
      console.log('Transaction Details:');
      console.log(`  ID: ${result.transaction.id}`);
      console.log(`  Gateway: ${result.transaction.gateway}`);
      console.log(`  Type: ${result.transaction.transferType}`);
      console.log(`  Amount: ${result.transaction.transferAmount.toLocaleString('vi-VN')} VND`);
      console.log(`  Reference: ${result.transaction.referenceCode}`);
      console.log(`  Content: ${result.transaction.content || 'N/A'}`);
      console.log(`\n  Incoming: ${result.isIncoming ? 'Yes' : 'No'}`);
      console.log(`  Outgoing: ${result.isOutgoing ? 'Yes' : 'No'}`);
    } else {
      console.error('✗ Verification failed:', result.error);
      process.exit(1);
    }
  } catch (error) {
    console.error('✗ Error:', error.message);
    process.exit(1);
  }
}

module.exports = SePayWebhookVerifier;
