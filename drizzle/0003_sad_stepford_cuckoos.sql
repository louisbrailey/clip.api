CREATE TABLE `agent_routes` (
	`owner` text NOT NULL,
	`scope` text NOT NULL,
	`role` text NOT NULL,
	`agent` text,
	`revision` integer DEFAULT 1 NOT NULL,
	PRIMARY KEY(`owner`, `scope`, `role`)
);
--> statement-breakpoint
CREATE INDEX `agent_routes_target` ON `agent_routes` (`owner`,`agent`,`scope`,`role`);--> statement-breakpoint
ALTER TABLE `agents` ADD `task_role` text DEFAULT 'writer' NOT NULL;--> statement-breakpoint
ALTER TABLE `agents` ADD `core` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE `agents` ADD `archived` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE `agents` ADD `depth` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE `agents` ADD `revision` integer DEFAULT 1 NOT NULL;--> statement-breakpoint
ALTER TABLE `agents` ADD `child_count` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE `agents` ADD `search_name` text DEFAULT '' NOT NULL;--> statement-breakpoint
CREATE INDEX `agents_children` ON `agents` (`owner`,`parent`,`id`);--> statement-breakpoint
CREATE INDEX `agents_retirement` ON `agents` (`owner`,`parent`,`archived`);--> statement-breakpoint
CREATE INDEX `agents_search` ON `agents` (`owner`,`search_name`,`id`);--> statement-breakpoint
CREATE INDEX `agents_core` ON `agents` (`owner`,`core`);--> statement-breakpoint
ALTER TABLE `settings` ADD `agent_total` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
CREATE INDEX `jobs_agent_status` ON `jobs` (`owner`,`agent`,`status`);
--> statement-breakpoint
UPDATE agents SET core=1, task_role=CASE WHEN id='astra' THEN 'orchestrator' WHEN parent='astra' THEN 'lead' WHEN id LIKE '%-writer' THEN 'writer' ELSE 'editor' END,
  depth=CASE WHEN id='astra' THEN 0 WHEN parent='astra' THEN 1 ELSE 2 END,
  search_name=lower(name),child_count=(SELECT COUNT(*) FROM agents child WHERE child.owner=agents.owner AND child.parent=agents.id);
--> statement-breakpoint
UPDATE settings SET agent_total=(SELECT COUNT(*) FROM agents a WHERE a.owner=settings.owner);
