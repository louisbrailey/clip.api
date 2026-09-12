"use client";
import { useState, type FormEvent, type ReactNode } from "react";
import { CalendarClock, Pause, Play, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Schedule, State } from "@/lib/domain";
import { platformInfo } from "@/lib/domain";

const when = (n: number) => new Date(n).toLocaleString();
const localDate = (n: number) => {
  const d = new Date(n);
  return new Date(n - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
export function SchedulePanel({
  state: s,
  busy,
  offset,
  search,
  onSearch,
  onPage,
  onEdit,
  onRun,
  act,
}: {
  state: State;
  busy: boolean;
  offset: number;
  search: string;
  onSearch: (value: string) => void;
  onPage: (value: number) => void;
  onEdit: (value: Schedule | null) => void;
  onRun: (id: string) => void;
  act: (body: Record<string, unknown>, success?: string) => Promise<unknown>;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>
            Recurring production{" "}
            <span className="count-pill">{s.schedule_total}</span>
          </h2>
          <p>
            Account-specific briefs, on a repeatable schedule. Live runs need
            the worker online; rehearsals advance from the work queue.
          </p>
        </div>
        <Button onClick={() => onEdit(null)} disabled={busy}>
          <Plus size={15} /> New schedule
        </Button>
      </div>
      <div className="inset-note">
        Pausing holds future runs and waiting tasks. Running calls may finish.
        Missed intervals combine into one catch-up run; failed runs wait for
        review. Publishing is approved separately.
      </div>
      <form
        className="search-bar"
        onSubmit={(e) => {
          e.preventDefault();
          onSearch(String(new FormData(e.currentTarget).get("q") || ""));
        }}
      >
        <Input
          name="q"
          aria-label="Search schedules by title or account"
          placeholder="Search schedule title or account"
          maxLength={120}
          defaultValue={search}
        />
        <Button type="submit" variant="outline">
          Search
        </Button>
      </form>
      {s.schedules.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Schedule / account</th>
                <th>Cadence</th>
                <th>Progress</th>
                <th>Dispatch</th>
                <th>Controls</th>
              </tr>
            </thead>
            <tbody>
              {s.schedules.map((r) => {
                const held =
                  !!r.paused ||
                  !!r.account_paused ||
                  !!s.settings.paused ||
                  s.agents.some(
                    (a) => (a.id === "astra" || a.id === r.lane) && a.paused,
                  );
                const exhausted =
                  r.max_runs !== null && r.generated_count >= r.max_runs;
                const status = held
                  ? "paused"
                  : r.review
                    ? "needs review"
                    : r.pending
                      ? "in progress"
                      : exhausted
                        ? "complete"
                        : "scheduled";
                return (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.title}</strong>
                      <small>
                        {r.handle} ·{" "}
                        {platformInfo[r.platform]?.name || r.platform}
                      </small>
                      <small>{r.mode}</small>
                    </td>
                    <td>
                      Every{" "}
                      {r.interval_minutes >= 1440 &&
                      r.interval_minutes % 1440 === 0
                        ? `${r.interval_minutes / 1440} day(s)`
                        : r.interval_minutes % 60 === 0
                          ? `${r.interval_minutes / 60} hour(s)`
                          : `${r.interval_minutes} min`}
                      <small>
                        {exhausted
                          ? "Run limit reached"
                          : `Next: ${when(r.next_run)}`}
                      </small>
                    </td>
                    <td>
                      {r.generated_count}
                      {r.max_runs === null
                        ? " runs created"
                        : ` / ${r.max_runs} runs created`}
                      <small>{r.pending} unfinished tasks</small>
                    </td>
                    <td>
                      <span className={`badge ${status.replaceAll(" ", "-")}`}>
                        {status}
                      </span>
                    </td>
                    <td>
                      <div className="button-row">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busy}
                          onClick={() => onEdit(r)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busy}
                          onClick={() =>
                            act(
                              {
                                action: "schedule-pause",
                                id: r.id,
                                revision: r.revision,
                                paused: !r.paused,
                              },
                              r.paused
                                ? "Schedule resumed"
                                : "Schedule paused; waiting work held",
                            )
                          }
                        >
                          {r.paused ? <Play size={13} /> : <Pause size={13} />}{" "}
                          {r.paused ? "Resume" : "Pause"}
                        </Button>
                        {!!r.generated_count && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onRun(r.id)}
                          >
                            View runs
                          </Button>
                        )}
                        {r.pending > 0 &&
                          r.running === 0 &&
                          r.pending_occurrence !== null && (
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              onClick={() =>
                                act(
                                  {
                                    action: "schedule-discard",
                                    id: r.id,
                                    occurrence: r.pending_occurrence,
                                  },
                                  "Waiting run discarded; future recurrence remains scheduled",
                                )
                              }
                            >
                              Discard waiting run
                            </Button>
                          )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <CalendarClock />
          <h3>Set your production rhythm</h3>
          <p>
            Register an authorized account, then add its audience, creative
            direction and cadence.
          </p>
        </div>
      )}
      <div className="button-row">
        <Button
          variant="outline"
          size="sm"
          disabled={!offset}
          onClick={() => onPage(Math.max(0, offset - 60))}
        >
          Previous
        </Button>
        <span>
          {s.schedule_total
            ? `${offset + 1}–${Math.min(offset + 60, s.schedule_total)} of ${s.schedule_total}`
            : "No schedules"}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={offset + 60 >= s.schedule_total}
          onClick={() => onPage(offset + 60)}
        >
          Next
        </Button>
      </div>
    </section>
  );
}
export function ScheduleForm({
  value: r,
  busy,
  children,
  onSubmit,
}: {
  value: Schedule | null;
  busy: boolean;
  children: ReactNode;
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
}) {
  const [requestId] = useState(() => crypto.randomUUID());
  return (
    <form className="form" onSubmit={onSubmit}>
      {!r && <input type="hidden" name="request_id" value={requestId} />}
      {r ? (
        <>
          <input type="hidden" name="id" value={r.id} />
          <input type="hidden" name="revision" value={r.revision} />
          <input type="hidden" name="account" value={r.account} />
          <p className="inset-note">
            {r.handle} · {platformInfo[r.platform]?.name}. Changes apply to
            future occurrences; existing work retains its brief.
          </p>
        </>
      ) : (
        children
      )}
      <label className="field">
        <span>Schedule title</span>
        <Input
          name="title"
          defaultValue={r?.title}
          placeholder="Daily original breathing meditation"
          minLength={3}
          maxLength={160}
          required
        />
      </label>
      <label className="field">
        <span>Account-specific production brief</span>
        <textarea
          name="brief"
          defaultValue={r?.brief}
          rows={5}
          minLength={15}
          maxLength={6000}
          required
          placeholder="Audience, style, recurring topics, original or licensed sources, and the output this account needs…"
        />
      </label>
      <div className="form-two">
        <label className="field">
          <span>Execution</span>
          <select name="mode" defaultValue={r?.mode || "rehearsal"}>
            <option value="rehearsal">Rehearsal · no model calls</option>
            <option value="live">Live · connected worker required</option>
          </select>
        </label>
        <label className="field">
          <span>Repeat every (minutes)</span>
          <Input
            name="interval_minutes"
            type="number"
            min={60}
            max={525600}
            defaultValue={r?.interval_minutes || 1440}
            required
          />
          <small>60 = hourly · 1,440 = daily · 10,080 = weekly</small>
        </label>
      </div>
      <div className="form-two">
        <label className="field">
          <span>Next run (local time)</span>
          <Input
            name="next_run"
            type="datetime-local"
            defaultValue={localDate(r?.next_run || Date.now())}
            required
          />
          <small>
            Intervals use elapsed time. Daylight-saving changes can shift the
            local hour.
          </small>
        </label>
        <label className="field">
          <span>Total run limit (optional)</span>
          <Input
            name="max_runs"
            type="number"
            min={1}
            max={1000000}
            defaultValue={r?.max_runs ?? ""}
          />
          <small>
            Blank repeats until paused. Existing run count is retained.
          </small>
        </label>
      </div>
      <label className="checkbox">
        <input type="checkbox" name="paused" defaultChecked={!!r?.paused} />
        <span>Keep this schedule paused</span>
      </label>
      <p className="inset-note">
        Astra delegates each brief to the account’s studio. This creates scripts
        and editorial packages; it grants no automatic publishing approval.
      </p>
      <Button type="submit" disabled={busy}>
        Save schedule
      </Button>
    </form>
  );
}
