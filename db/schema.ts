import { sql } from "drizzle-orm";
import {
  sqliteTable,
  text,
  integer,
  primaryKey,
  index,
  uniqueIndex,
} from "drizzle-orm/sqlite-core";
export const settings = sqliteTable(
  "settings",
  {
    owner: text().primaryKey(),
    paused: integer().notNull().default(0),
    concurrency: integer().notNull().default(4),
    daily_tokens: integer().notNull().default(100000),
    worker_hash: text(),
    worker_seen: integer(),
  },
  (t) => [uniqueIndex("settings_worker_hash").on(t.worker_hash)],
);
export const agents = sqliteTable(
  "agents",
  {
    owner: text().notNull(),
    id: text().notNull(),
    parent: text(),
    name: text().notNull(),
    role: text().notNull(),
    lane: text().notNull(),
    model: text().notNull(),
    paused: integer().notNull().default(0),
    concurrency: integer().notNull().default(2),
    instructions: text().notNull(),
    color: text().notNull(),
  },
  (t) => [primaryKey({ columns: [t.owner, t.id] })],
);
export const accounts = sqliteTable(
  "accounts",
  {
    id: text().primaryKey(),
    owner: text().notNull(),
    platform: text().notNull(),
    handle: text().notNull(),
    lane: text().notNull(),
    external_id: text().notNull(),
    credential_ref: text().notNull(),
    authorized: integer().notNull(),
    paused: integer().notNull().default(0),
    daily_limit: integer().notNull().default(1),
    created: integer().notNull(),
  },
  (t) => [
    uniqueIndex("account_identity").on(t.owner, t.platform, t.external_id),
    index("accounts_owner_created").on(t.owner, t.created),
  ],
);
export const assets = sqliteTable(
  "assets",
  {
    id: text().primaryKey(),
    owner: text().notNull(),
    name: text().notNull(),
    object_key: text().notNull(),
    mime: text().notNull(),
    size: integer().notNull(),
    rights: text().notNull(),
    evidence: text().notNull(),
    expires: integer(),
    created: integer().notNull(),
  },
  (t) => [index("assets_owner_created").on(t.owner, t.created)],
);
export const jobs = sqliteTable(
  "jobs",
  {
    id: text().primaryKey(),
    owner: text().notNull(),
    parent: text(),
    depends: text(),
    agent: text().notNull(),
    title: text().notNull(),
    brief: text().notNull(),
    kind: text().notNull(),
    mode: text().notNull(),
    status: text().notNull().default("queued"),
    lane: text().notNull(),
    result: text().notNull().default(""),
    error: text().notNull().default(""),
    created: integer().notNull(),
    scheduled: integer().notNull(),
    attempts: integer().notNull().default(0),
    tokens: integer().notNull().default(0),
    reserve: integer().notNull().default(0),
    billed_day: integer().notNull().default(0),
    lease: text(),
    lease_until: integer(),
    account: text(),
    asset: text(),
    receipt: text().notNull().default(""),
    completion_nonce: text(),
    completion_hash: text(),
    approved: integer().notNull().default(0),
    schedule_id: text(),
    occurrence: integer(),
  },
  (t) => [
    index("jobs_claim").on(t.owner, t.mode, t.status, t.scheduled),
    index("jobs_parent").on(t.owner, t.parent),
    index("jobs_budget").on(t.owner, t.created),
    index("jobs_account").on(t.owner, t.account, t.status),
    index("jobs_recent").on(t.owner, t.created),
    uniqueIndex("jobs_publish_once")
      .on(t.owner, t.asset)
      .where(
        sql`kind='publish' AND status IN ('queued','running','uncertain','succeeded')`,
      ),
    index("jobs_lease").on(t.owner, t.lease),
    index("jobs_schedule_status").on(t.owner, t.schedule_id, t.status),
    uniqueIndex("jobs_schedule_occurrence")
      .on(t.owner, t.schedule_id, t.occurrence)
      .where(sql`parent IS NULL AND schedule_id IS NOT NULL`),
  ],
);
export const events = sqliteTable(
  "events",
  {
    id: text().primaryKey(),
    owner: text().notNull(),
    message: text().notNull(),
    type: text().notNull(),
    job: text(),
    created: integer().notNull(),
  },
  (t) => [index("events_recent").on(t.owner, t.created)],
);

export const usage = sqliteTable(
  "usage",
  {
    id: text().primaryKey(),
    owner: text().notNull(),
    day: integer().notNull(),
    tokens: integer().notNull(),
  },
  (t) => [index("usage_owner_day").on(t.owner, t.day)],
);

export const schedules = sqliteTable(
  "schedules",
  {
    id: text().primaryKey(),
    owner: text().notNull(),
    account: text().notNull(),
    title: text().notNull(),
    brief: text().notNull(),
    mode: text().notNull(),
    interval_minutes: integer().notNull(),
    next_run: integer().notNull(),
    paused: integer().notNull().default(0),
    generated_count: integer().notNull().default(0),
    max_runs: integer(),
    revision: integer().notNull().default(1),
    created: integer().notNull(),
    updated: integer().notNull(),
  },
  (t) => [
    index("schedules_due").on(t.owner, t.mode, t.paused, t.next_run),
    index("schedules_account").on(t.owner, t.account),
  ],
);
