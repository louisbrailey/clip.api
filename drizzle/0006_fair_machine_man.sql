ALTER TABLE `schedules` ADD `production_kind` text DEFAULT 'workflow' NOT NULL;--> statement-breakpoint
ALTER TABLE `schedules` ADD `render_recipe` text;--> statement-breakpoint
ALTER TABLE `schedules` ADD `render_approved` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE `schedules` ADD `creation_hash` text;