import {
  FleetEntityType,
  FleetOfflineTransaction,
  FleetSyncBatchResponse,
  registerFleetBranch,
  submitFleetSyncBatch,
} from './api';

const DATABASE_NAME = 'gfi-fleet-edge';
const DATABASE_VERSION = 1;
const STATE_STORE = 'state';
const QUEUE_STORE = 'queue';

interface StoredValue<T> {
  key: string;
  value: T;
}

interface FleetIdentity {
  branchId: string;
  deviceFingerprint: string;
  locationName: string;
  signingKey: CryptoKey;
}

interface QueuedTransaction extends FleetOfflineTransaction {
  localState: 'queued' | 'conflict';
  conflictDetail?: string | null;
}

interface EncryptedQueueItem {
  id: string;
  nonce: string;
  ciphertext: string;
}

export interface FleetQueueSummary {
  transaction_id: string;
  entity_type: FleetEntityType;
  record_id: string;
  client_updated_at: string;
  state: 'queued' | 'conflict';
  conflict_detail?: string | null;
}

function getClinicStorageScope(): string {
  const token = window.localStorage.getItem('access_token');
  const encodedPayload = token?.split('.')[1];
  if (!encodedPayload) throw new Error('Sign in before accessing this clinic offline store.');
  try {
    const base64 = encodedPayload.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '='))) as { clinic_id?: number | string };
    if (payload.clinic_id === undefined || payload.clinic_id === null) throw new Error('Missing clinic context');
    return String(payload.clinic_id).replace(/[^a-zA-Z0-9_-]/g, '_');
  } catch {
    throw new Error('Session has no valid clinic context. Sign in again.');
  }
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(`${DATABASE_NAME}-${getClinicStorageScope()}`, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STATE_STORE)) {
        database.createObjectStore(STATE_STORE, { keyPath: 'key' });
      }
      if (!database.objectStoreNames.contains(QUEUE_STORE)) {
        database.createObjectStore(QUEUE_STORE, { keyPath: 'id' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Unable to open local sync database.'));
  });
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Local sync storage request failed.'));
  });
}

async function readState<T>(key: string): Promise<T | undefined> {
  const database = await openDatabase();
  try {
    const transaction = database.transaction(STATE_STORE, 'readonly');
    const result = await requestResult(transaction.objectStore(STATE_STORE).get(key)) as StoredValue<T> | undefined;
    return result?.value;
  } finally {
    database.close();
  }
}

async function writeState<T>(key: string, value: T): Promise<void> {
  const database = await openDatabase();
  try {
    const transaction = database.transaction(STATE_STORE, 'readwrite');
    const completed = new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error('Unable to save local sync state.'));
      transaction.onabort = () => reject(transaction.error ?? new Error('Local sync state save was aborted.'));
    });
    transaction.objectStore(STATE_STORE).put({ key, value } satisfies StoredValue<T>);
    await completed;
  } finally {
    database.close();
  }
}

async function getEncryptionKey(): Promise<CryptoKey> {
  const existing = await readState<CryptoKey>('queue-encryption-key');
  if (existing) return existing;
  const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  await writeState('queue-encryption-key', key);
  return key;
}

function toBase64(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function fromBase64(value: string): Uint8Array {
  const binary = atob(value);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export async function getFleetIdentitySummary(): Promise<Omit<FleetIdentity, 'signingKey'> | null> {
  const identity = await readState<FleetIdentity>('branch-identity');
  if (!identity) return null;
  return {
    branchId: identity.branchId,
    deviceFingerprint: identity.deviceFingerprint,
    locationName: identity.locationName,
  };
}

export async function registerFleetDevice(locationName: string): Promise<Omit<FleetIdentity, 'signingKey'>> {
  const existing = await getFleetIdentitySummary();
  if (existing) return existing;

  if (!crypto.subtle || !indexedDB) throw new Error('This browser does not support secure offline storage.');
  try {
    const pair = await crypto.subtle.generateKey(
      { name: 'Ed25519' } as AlgorithmIdentifier,
      true,
      ['sign', 'verify'],
    ) as CryptoKeyPair;
    const [rawPublicKey, exportedPrivateKey] = await Promise.all([
      crypto.subtle.exportKey('raw', pair.publicKey),
      crypto.subtle.exportKey('pkcs8', pair.privateKey),
    ]);
    const privateBytes = new Uint8Array(exportedPrivateKey);
    const nonExtractablePrivateKey = await crypto.subtle.importKey(
      'pkcs8',
      privateBytes,
      { name: 'Ed25519' } as AlgorithmIdentifier,
      false,
      ['sign'],
    );
    privateBytes.fill(0);
    const publicBytes = new Uint8Array(rawPublicKey);
    const publicKey = toBase64(publicBytes);
    const deviceFingerprint = toHex(new Uint8Array(await crypto.subtle.digest('SHA-256', rawPublicKey)));
    const registration = await registerFleetBranch(locationName, publicKey);
    const identity: FleetIdentity = {
      branchId: registration.branch_id,
      deviceFingerprint,
      locationName: registration.location_name,
      signingKey: nonExtractablePrivateKey,
    };
    await writeState('branch-identity', identity);
    await getEncryptionKey();
    return {
      branchId: identity.branchId,
      deviceFingerprint: identity.deviceFingerprint,
      locationName: identity.locationName,
    };
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : 'Secure device registration failed.');
  }
}

async function storeEncrypted(item: QueuedTransaction): Promise<void> {
  const key = await getEncryptionKey();
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(JSON.stringify(item));
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, plaintext);
  const stored: EncryptedQueueItem = {
    id: item.transaction_id,
    nonce: toBase64(nonce),
    ciphertext: toBase64(new Uint8Array(ciphertext)),
  };

  const database = await openDatabase();
  try {
    const transaction = database.transaction(QUEUE_STORE, 'readwrite');
    const completed = new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error('Unable to save offline transaction.'));
      transaction.onabort = () => reject(transaction.error ?? new Error('Offline transaction save was aborted.'));
    });
    transaction.objectStore(QUEUE_STORE).put(stored);
    await completed;
  } finally {
    database.close();
  }
}

async function readQueue(): Promise<QueuedTransaction[]> {
  const key = await getEncryptionKey();
  const database = await openDatabase();
  try {
    const transaction = database.transaction(QUEUE_STORE, 'readonly');
    const stored = await requestResult(transaction.objectStore(QUEUE_STORE).getAll()) as EncryptedQueueItem[];
    const decrypted = await Promise.all(stored.map(async (item) => {
      const plaintext = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: fromBase64(item.nonce) },
        key,
        fromBase64(item.ciphertext),
      );
      return JSON.parse(new TextDecoder().decode(plaintext)) as QueuedTransaction;
    }));
    return decrypted.sort((left, right) => left.client_updated_at.localeCompare(right.client_updated_at));
  } finally {
    database.close();
  }
}

export async function queueFleetDiff(
  entityType: FleetEntityType,
  recordId: string,
  changes: Record<string, unknown>,
): Promise<void> {
  const transaction: QueuedTransaction = {
    transaction_id: crypto.randomUUID(),
    entity_type: entityType,
    record_id: recordId.trim(),
    client_updated_at: new Date().toISOString(),
    changes,
    localState: 'queued',
  };
  await storeEncrypted(transaction);
}

export async function getFleetQueueSummary(): Promise<FleetQueueSummary[]> {
  const queue = await readQueue();
  return queue.map((item) => ({
    transaction_id: item.transaction_id,
    entity_type: item.entity_type,
    record_id: item.record_id,
    client_updated_at: item.client_updated_at,
    state: item.localState,
    conflict_detail: item.conflictDetail,
  }));
}

function sortRecursively(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortRecursively);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(
        ([key, child]) => [key, sortRecursively(child)],
      ),
    );
  }
  return value;
}

export async function syncFleetQueue(): Promise<FleetSyncBatchResponse | null> {
  const identity = await readState<FleetIdentity>('branch-identity');
  if (!identity) throw new Error('Register this branch device before syncing.');
  const queued = (await readQueue()).filter((item) => item.localState === 'queued').slice(0, 100);
  if (!queued.length) return null;

  const unsigned = {
    batch_id: crypto.randomUUID(),
    branch_id: identity.branchId,
    transactions: queued.map(({ localState: _localState, conflictDetail: _conflictDetail, ...transaction }) => transaction),
  };
  const signedPayload = JSON.stringify(sortRecursively(unsigned));
  const message = new TextEncoder().encode(signedPayload);
  const signature = toBase64(new Uint8Array(await crypto.subtle.sign('Ed25519', identity.signingKey, message)));
  const response = await submitFleetSyncBatch({ signed_payload: signedPayload, signature });
  const resultMap = new Map(response.results.map((result) => [result.transaction_id, result]));

  for (const transaction of queued) {
    const result = resultMap.get(transaction.transaction_id);
    if (!result) continue;
    if (result.status === 'applied') {
      await deleteQueueItem(transaction.transaction_id);
    } else {
      await storeEncrypted({
        ...transaction,
        localState: 'conflict',
        conflictDetail: result.detail ?? result.status,
      });
    }
  }
  return response;
}

async function deleteQueueItem(id: string): Promise<void> {
  const database = await openDatabase();
  try {
    const transaction = database.transaction(QUEUE_STORE, 'readwrite');
    const completed = new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error('Unable to remove synced transaction.'));
      transaction.onabort = () => reject(transaction.error ?? new Error('Queue update was aborted.'));
    });
    transaction.objectStore(QUEUE_STORE).delete(id);
    await completed;
  } finally {
    database.close();
  }
}

export async function discardFleetQueueItem(id: string): Promise<void> {
  await deleteQueueItem(id);
}