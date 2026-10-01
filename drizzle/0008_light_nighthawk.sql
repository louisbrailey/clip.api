CREATE TABLE `workers` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`name` text NOT NULL,
	`key_hash` text NOT NULL,
	`paused` integer DEFAULT 0 NOT NULL,
	`concurrency` integer DEFAULT 2 NOT NULL,
	`last_seen` integer,
	`revision` integer DEFAULT 1 NOT NULL,
	`revoked` integer DEFAULT 0 NOT NULL,
	`created` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `workers_key_hash` ON `workers` (`key_hash`);--> statement-breakpoint
CREATE INDEX `workers_owner_created` ON `workers` (`owner`,`created`);--> statement-breakpoint
INSERT INTO `workers` (`id`,`owner`,`name`,`key_hash`,`concurrency`,`last_seen`,`created`)
SELECT 'legacy-' || substr(`worker_hash`,1,29),`owner`,'Primary worker',`worker_hash`,2,`worker_seen`,0
FROM `settings` WHERE `worker_hash` IS NOT NULL;--> statement-breakpoint
ALTER TABLE `jobs` ADD `worker_id` text;--> statement-breakpoint
CREATE INDEX `jobs_worker_status` ON `jobs` (`owner`,`worker_id`,`status`);
