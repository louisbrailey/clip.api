CREATE TABLE `schedules` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`account` text NOT NULL,
	`title` text NOT NULL,
	`brief` text NOT NULL,
	`mode` text NOT NULL,
	`interval_minutes` integer NOT NULL,
	`next_run` integer NOT NULL,
	`paused` integer DEFAULT 0 NOT NULL,
	`generated_count` integer DEFAULT 0 NOT NULL,
	`max_runs` integer,
	`revision` integer DEFAULT 1 NOT NULL,
	`created` integer NOT NULL,
	`updated` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `schedules_due` ON `schedules` (`owner`,`mode`,`paused`,`next_run`);--> statement-breakpoint
CREATE INDEX `schedules_account` ON `schedules` (`owner`,`account`);--> statement-breakpoint
ALTER TABLE `jobs` ADD `schedule_id` text;--> statement-breakpoint
ALTER TABLE `jobs` ADD `occurrence` integer;--> statement-breakpoint
CREATE INDEX `jobs_schedule_status` ON `jobs` (`owner`,`schedule_id`,`status`);--> statement-breakpoint
CREATE UNIQUE INDEX `jobs_schedule_occurrence` ON `jobs` (`owner`,`schedule_id`,`occurrence`) WHERE parent IS NULL AND schedule_id IS NOT NULL;