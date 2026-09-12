CREATE TABLE `usage` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`day` integer NOT NULL,
	`tokens` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `usage_owner_day` ON `usage` (`owner`,`day`);--> statement-breakpoint
ALTER TABLE `jobs` ADD `completion_nonce` text;--> statement-breakpoint
ALTER TABLE `jobs` ADD `completion_hash` text;--> statement-breakpoint
CREATE UNIQUE INDEX `jobs_publish_once` ON `jobs` (`owner`,`asset`) WHERE kind='publish' AND status IN ('queued','running','uncertain','succeeded');--> statement-breakpoint
CREATE INDEX `jobs_lease` ON `jobs` (`owner`,`lease`);