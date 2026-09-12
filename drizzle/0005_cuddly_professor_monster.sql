ALTER TABLE `assets` ADD `source_job` text;--> statement-breakpoint
ALTER TABLE `assets` ADD `sha256` text;--> statement-breakpoint
CREATE UNIQUE INDEX `assets_source_job` ON `assets` (`owner`,`source_job`);--> statement-breakpoint
ALTER TABLE `jobs` ADD `render_spec` text;