CREATE TABLE `accounts` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`platform` text NOT NULL,
	`handle` text NOT NULL,
	`lane` text NOT NULL,
	`external_id` text NOT NULL,
	`credential_ref` text NOT NULL,
	`authorized` integer NOT NULL,
	`paused` integer DEFAULT 0 NOT NULL,
	`daily_limit` integer DEFAULT 1 NOT NULL,
	`created` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `account_identity` ON `accounts` (`owner`,`platform`,`external_id`);--> statement-breakpoint
CREATE INDEX `accounts_owner_created` ON `accounts` (`owner`,`created`);--> statement-breakpoint
CREATE TABLE `agents` (
	`owner` text NOT NULL,
	`id` text NOT NULL,
	`parent` text,
	`name` text NOT NULL,
	`role` text NOT NULL,
	`lane` text NOT NULL,
	`model` text NOT NULL,
	`paused` integer DEFAULT 0 NOT NULL,
	`concurrency` integer DEFAULT 2 NOT NULL,
	`instructions` text NOT NULL,
	`color` text NOT NULL,
	PRIMARY KEY(`owner`, `id`)
);
--> statement-breakpoint
CREATE TABLE `assets` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`name` text NOT NULL,
	`object_key` text NOT NULL,
	`mime` text NOT NULL,
	`size` integer NOT NULL,
	`rights` text NOT NULL,
	`evidence` text NOT NULL,
	`expires` integer,
	`created` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `assets_owner_created` ON `assets` (`owner`,`created`);--> statement-breakpoint
CREATE TABLE `events` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`message` text NOT NULL,
	`type` text NOT NULL,
	`job` text,
	`created` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `events_recent` ON `events` (`owner`,`created`);--> statement-breakpoint
CREATE TABLE `jobs` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`parent` text,
	`depends` text,
	`agent` text NOT NULL,
	`title` text NOT NULL,
	`brief` text NOT NULL,
	`kind` text NOT NULL,
	`mode` text NOT NULL,
	`status` text DEFAULT 'queued' NOT NULL,
	`lane` text NOT NULL,
	`result` text DEFAULT '' NOT NULL,
	`error` text DEFAULT '' NOT NULL,
	`created` integer NOT NULL,
	`scheduled` integer NOT NULL,
	`attempts` integer DEFAULT 0 NOT NULL,
	`tokens` integer DEFAULT 0 NOT NULL,
	`reserve` integer DEFAULT 0 NOT NULL,
	`billed_day` integer DEFAULT 0 NOT NULL,
	`lease` text,
	`lease_until` integer,
	`account` text,
	`asset` text,
	`receipt` text DEFAULT '' NOT NULL,
	`approved` integer DEFAULT 0 NOT NULL
);
--> statement-breakpoint
CREATE INDEX `jobs_claim` ON `jobs` (`owner`,`mode`,`status`,`scheduled`);--> statement-breakpoint
CREATE INDEX `jobs_parent` ON `jobs` (`owner`,`parent`);--> statement-breakpoint
CREATE INDEX `jobs_budget` ON `jobs` (`owner`,`created`);--> statement-breakpoint
CREATE INDEX `jobs_account` ON `jobs` (`owner`,`account`,`status`);--> statement-breakpoint
CREATE INDEX `jobs_recent` ON `jobs` (`owner`,`created`);--> statement-breakpoint
CREATE TABLE `settings` (
	`owner` text PRIMARY KEY NOT NULL,
	`paused` integer DEFAULT 0 NOT NULL,
	`concurrency` integer DEFAULT 4 NOT NULL,
	`daily_tokens` integer DEFAULT 100000 NOT NULL,
	`worker_hash` text,
	`worker_seen` integer
);
--> statement-breakpoint
CREATE UNIQUE INDEX `settings_worker_hash` ON `settings` (`worker_hash`);