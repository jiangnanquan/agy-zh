'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { resolveAntigravityPath } = require('../paths.js');
const { mergeQuotaWindows } = require('./models.js');

const CACHE_PATH = resolveAntigravityPath('agy-hud-quota-cache.json');
const CACHE_VERSION = 4;

function isCachePayloadFresh(raw) {
  return raw &&
    (raw.version === CACHE_VERSION || raw.version === 3) &&
    raw.expiresAt &&
    Date.now() < raw.expiresAt &&
    Array.isArray(raw.data);
}

function hashCacheKey(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function normalizeTokenCacheInput(tokenOrAccessToken) {
  if (typeof tokenOrAccessToken === 'string') {
    return { accessToken: tokenOrAccessToken };
  }
  if (!tokenOrAccessToken || typeof tokenOrAccessToken !== 'object') {
    return null;
  }
  return tokenOrAccessToken;
}

function getTokenCacheIdentity(tokenOrAccessToken) {
  const token = normalizeTokenCacheInput(tokenOrAccessToken);
  if (!token) return null;

  if (token.sourcePath) {
    return `sourcePath:${path.resolve(token.sourcePath)}`;
  }

  if (token.refreshToken) {
    return `refreshToken:${token.refreshToken}`;
  }

  if (token.accountEmail) {
    return `accountEmail:${token.accountEmail}`;
  }

  if (token.sourceFormat) {
    return `sourceFormat:${token.sourceFormat}`;
  }

  if (token.accessToken) {
    return `accessToken:${token.accessToken}`;
  }

  return null;
}

function getTokenHash(tokenOrAccessToken) {
  const token = normalizeTokenCacheInput(tokenOrAccessToken);
  if (!token || !token.accessToken) return null;
  return hashCacheKey(token.accessToken);
}

function getTokenCacheKeyHash(tokenOrAccessToken) {
  const identity = getTokenCacheIdentity(tokenOrAccessToken);
  return identity ? hashCacheKey(identity) : null;
}

function doesCachePayloadMatchToken(raw, tokenOrAccessToken, expectedEmail = null) {
  if (!raw || !Array.isArray(raw.data)) return false;

  const token = normalizeTokenCacheInput(tokenOrAccessToken);
  if (!token) return false;

  const effectiveEmail = expectedEmail || token.accountEmail;
  if (effectiveEmail && raw.accountEmail && raw.accountEmail !== effectiveEmail) {
    return false;
  }

  const tokenHash = getTokenHash(token);
  if (raw.tokenHash && tokenHash && raw.tokenHash === tokenHash) {
    return true;
  }

  if (token.refreshToken && raw.refreshTokenHash) {
    if (hashCacheKey(token.refreshToken) === raw.refreshTokenHash) {
      return true;
    }
  }

  if (token.accountEmail && raw.accountEmail && token.accountEmail === raw.accountEmail) {
    return true;
  }

  if (token.sourcePath) {
    const cacheKeyHash = getTokenCacheKeyHash(token);
    if (raw.cacheKeyHash && cacheKeyHash && raw.cacheKeyHash === cacheKeyHash) {
      if (!effectiveEmail || !raw.accountEmail || raw.accountEmail === effectiveEmail) {
        return true;
      }
    }
  }

  return false;
}

function didAccessTokenRotate(raw, tokenOrAccessToken) {
  const tokenHash = getTokenHash(tokenOrAccessToken);
  return Boolean(raw && raw.tokenHash && tokenHash && raw.tokenHash !== tokenHash);
}

/**
 * Read cached quota if still valid.
 * @param {string|Object} tokenOrAccessToken
 * @param {string|null} [accountEmail]
 * @returns {ModelQuota[] | null}
 */
function readCache(tokenOrAccessToken, accountEmail = null) {
  try {
    const payload = readCachePayload(tokenOrAccessToken, accountEmail);
    if (!payload || !isCachePayloadFresh(payload)) return null;
    return payload.data;
  } catch {
    return null;
  }
}

/**
 * Read the previous cache payload (any token) for merging the other window's
 * last observation.
 */
function readCacheRaw() {
  try {
    const raw = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    if (!raw || !Array.isArray(raw.data)) return null;
    return raw;
  } catch {
    return null;
  }
}

/**
 * Write quota cache. Supports multi-account dictionary under payload.accounts[accountEmail]
 * to completely eliminate cross-account cache collisions on shared machines.
 */
function writeCache(data, tokenOrAccessToken, tier = null, accountEmail = null) {
  const now = Date.now();
  const previousRaw = readCacheRaw();
  const token = normalizeTokenCacheInput(tokenOrAccessToken);
  const targetEmail = accountEmail || token?.accountEmail;

  const accounts = (previousRaw && typeof previousRaw.accounts === 'object') ? { ...previousRaw.accounts } : {};
  const previousAccountEntry = (targetEmail && accounts[targetEmail]) ? accounts[targetEmail] : null;

  let sameIdentity = false;
  if (previousAccountEntry) {
    sameIdentity = doesCachePayloadMatchToken(previousAccountEntry, tokenOrAccessToken, targetEmail);
  } else if (previousRaw) {
    sameIdentity = doesCachePayloadMatchToken(previousRaw, tokenOrAccessToken, targetEmail);
    if (sameIdentity && targetEmail && previousRaw.accountEmail && targetEmail !== previousRaw.accountEmail) {
      sameIdentity = false;
    }
  }

  const previousData = sameIdentity ? (previousAccountEntry?.data || previousRaw?.data || []) : [];
  const merged = mergeQuotaWindows(data, previousData, now);

  let earliest = Infinity;
  const considerResetTime = (value) => {
    if (!value) return;
    const t = new Date(value).getTime();
    if (Number.isFinite(t) && t < earliest) earliest = t;
  };
  for (const m of merged) {
    considerResetTime(m.resetTime);
    considerResetTime(m.windows?.fiveHour?.resetTime);
    considerResetTime(m.windows?.weekly?.resetTime);
  }
  const maxFreshDuration = 2 * 60 * 1000;
  let expiresAt = now + maxFreshDuration;
  if (isFinite(earliest) && earliest < expiresAt) {
    expiresAt = earliest;
  }

  const cacheKeyHash = getTokenCacheKeyHash(tokenOrAccessToken);
  const tokenHash = getTokenHash(tokenOrAccessToken);
  const refreshTokenHash = token?.refreshToken
    ? hashCacheKey(token.refreshToken)
    : (previousAccountEntry?.refreshTokenHash || (sameIdentity ? previousRaw?.refreshTokenHash : null) || null);

  const resolvedTier = tier || (sameIdentity ? (previousAccountEntry?.tier || previousRaw?.tier || null) : null);
  const resolvedEmail = targetEmail || (sameIdentity ? (previousAccountEntry?.accountEmail || previousRaw?.accountEmail || null) : null);

  if (resolvedEmail) {
    accounts[resolvedEmail] = {
      version: CACHE_VERSION,
      expiresAt,
      lastRefreshed: now,
      cacheKeyHash,
      tokenHash,
      refreshTokenHash,
      tier: resolvedTier,
      accountEmail: resolvedEmail,
      data: merged,
    };
  }

  const payload = {
    version: CACHE_VERSION,
    expiresAt,
    lastRefreshed: now,
    cacheKeyHash,
    tokenHash,
    refreshTokenHash,
    tier: resolvedTier,
    accountEmail: resolvedEmail,
    accounts,
    data: merged,
  };

  try {
    const tmpPath = `${CACHE_PATH}.tmp.${process.pid}`;
    fs.writeFileSync(tmpPath, JSON.stringify(payload), { mode: 0o600 });
    fs.renameSync(tmpPath, CACHE_PATH);
  } catch {
    try { fs.unlinkSync(`${CACHE_PATH}.tmp.${process.pid}`); } catch {}
  }
}

/**
 * Read the cached tier name, prioritizing the requested account email.
 * @param {string|null} [accountEmail]
 */
function getCachedTier(accountEmail = null) {
  try {
    const raw = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    if (!raw) return null;
    if (accountEmail && raw.accounts && raw.accounts[accountEmail]?.tier) {
      return raw.accounts[accountEmail].tier;
    }
    if (!accountEmail || raw.accountEmail === accountEmail) {
      return raw.tier || null;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Read the cached active-account email.
 * @param {string|Object} tokenOrAccessToken
 * @returns {string|null}
 */
function getCachedAccountEmail(tokenOrAccessToken) {
  try {
    const raw = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    if (!raw) return null;
    const token = normalizeTokenCacheInput(tokenOrAccessToken);
    if (!token) return null;

    const tokenHash = getTokenHash(token);
    if (raw.tokenHash && tokenHash && raw.tokenHash === tokenHash && raw.accountEmail) {
      return raw.accountEmail;
    }

    if (raw.accounts && typeof raw.accounts === 'object') {
      for (const [email, acc] of Object.entries(raw.accounts)) {
        if (acc && acc.tokenHash && tokenHash && acc.tokenHash === tokenHash) {
          return email;
        }
        if (token.refreshToken && acc.refreshTokenHash && hashCacheKey(token.refreshToken) === acc.refreshTokenHash) {
          return email;
        }
      }
    }

    if (doesCachePayloadMatchToken(raw, tokenOrAccessToken)) {
      return raw.accountEmail || null;
    }
    return null;
  } catch {
    return null;
  }
}

function readCachePayload(tokenOrAccessToken, accountEmail = null) {
  try {
    const raw = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    if (!raw) return null;

    const token = normalizeTokenCacheInput(tokenOrAccessToken);
    const targetEmail = accountEmail || token?.accountEmail;
    if (targetEmail && raw.accounts && raw.accounts[targetEmail]) {
      const acc = raw.accounts[targetEmail];
      if (isCachePayloadFresh(acc) && doesCachePayloadMatchToken(acc, tokenOrAccessToken, targetEmail)) {
        return acc;
      }
    }

    if (!doesCachePayloadMatchToken(raw, tokenOrAccessToken, targetEmail)) return null;
    return raw;
  } catch {
    return null;
  }
}

function readCacheLastRefreshed() {
  try {
    const raw = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    return raw.lastRefreshed || 0;
  } catch {
    return 0;
  }
}

function readCacheFallback(accountEmail = null) {
  try {
    const raw = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    if (!raw) return null;
    if (accountEmail && raw.accounts && raw.accounts[accountEmail]) {
      const acc = raw.accounts[accountEmail];
      if (Array.isArray(acc.data) && (acc.version === CACHE_VERSION || acc.version === 3)) {
        return acc;
      }
    }
    if (!Array.isArray(raw.data) || (raw.version !== CACHE_VERSION && raw.version !== 3)) return null;
    if (accountEmail && raw.accountEmail && raw.accountEmail !== accountEmail) return null;
    return raw;
  } catch {
    return null;
  }
}

module.exports = {
  CACHE_PATH,
  CACHE_VERSION,
  isCachePayloadFresh,
  hashCacheKey,
  getTokenCacheIdentity,
  getTokenHash,
  getTokenCacheKeyHash,
  doesCachePayloadMatchToken,
  didAccessTokenRotate,
  readCache,
  readCacheRaw,
  writeCache,
  getCachedTier,
  getCachedAccountEmail,
  readCachePayload,
  readCacheLastRefreshed,
  readCacheFallback,
};
