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
            Account-specific scripts or original ambient videos, on a repeatable
            schedule. Live runs need the worker online; rehearsals advance from
            the work queue.
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
                    (a) =>
                      (a.id === "astra" ||
                        a.id === r.lane ||
                        (r.production_kind === "ambient" &&
                          a.id === "ambient-editor")) &&
                      a.paused,
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
                      <small>
                        {r.production_kind === "ambient"
                          ? "Original ambient video"
                          : "Astra workflow"}{" "}
                        · {r.mode}
                      </small>
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
  children: (kind: "workflow" | "ambient") => ReactNode;
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
}) {
  const [requestId] = useState(() => crypto.randomUUID());
  const [kind, setKind] = useState<"workflow" | "ambient">(
    r?.production_kind || "workflow",
  );
  const [defaultRun] = useState(() => localDate(r?.next_run || Date.now()));
  let recipe: { seconds?: number; noise?: string; theme?: string; script?: string | null } = {};
  try {
    recipe = JSON.parse(r?.render_recipe || "{}");
  } catch {}
  return (
    <form className="form" onSubmit={onSubmit}>
      {!r && <input type="hidden" name="request_id" value={requestId} />}
      <label className="field">
        <span>What to produce</span>
        <select
          name={r ? undefined : "production_kind"}
          value={kind}
          disabled={!!r}
          onChange={(e) => setKind(e.target.value as "workflow" | "ambient")}
        >
          <option value="workflow">
            Astra workflow · scripts and editorial packages
          </option>
          <option value="ambient">
            Original ambient video · ready for library review
          </option>
        </select>
        {r && <input type="hidden" name="production_kind" value={kind} />}
        <small>
          {kind === "ambient"
            ? "Choose an authorized account in the Ambient studio. This uses the local renderer without model calls."
            : "Astra delegates a fresh creative brief to the account’s studio."}
        </small>
      </label>
      {r ? (
        <>
          <input type="hidden" name="id" value={r.id} />
          <input type="hidden" name="revision" value={r.revision} />
          <input type="hidden" name="account" value={r.account} />
          <p className="inset-note">
            {r.handle} · {platformInfo[r.platform]?.name}. Changes apply to
            future occurrences; existing work retains its saved settings.
          </p>
        </>
      ) : (
        children(kind)
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
        <span>
          {kind === "ambient"
            ? "Account notes for review"
            : "Account-specific production brief"}
        </span>
        <textarea
          name="brief"
          key={kind}
          defaultValue={
            r?.brief ||
            (kind === "ambient"
              ? "Create original ambient sound videos for this account. Review each result and approve publication separately."
              : "")
          }
          rows={5}
          minLength={15}
          maxLength={6000}
          required
          placeholder="Audience, style, recurring topics, original or licensed sources, and the output this account needs…"
        />
      </label>
      {kind === "ambient" && (
        <div className="form-two">
          <label className="field">
            <span>Noise texture</span>
            <select name="render_noise" defaultValue={recipe?.noise || "pink"}>
              <option value="pink">Pink · softer high frequencies</option>
              <option value="white">White · broadband</option>
              <option value="brown">Brown · deeper sound</option>
            </select>
          </label>
          <label className="field">
            <span>Visual color</span>
            <select name="render_theme" defaultValue={recipe?.theme || "night"}>
              <option value="night">Night · dark slate</option>
              <option value="ocean">Ocean · deep blue</option>
              <option value="forest">Forest · deep green</option>
            </select>
          </label>
          <label className="field">
            <span>Video duration (seconds)</span>
            <Input
              type="number"
              name="render_seconds"
              min={10}
              max={300}
              defaultValue={recipe?.seconds || 60}
              required
            />
            <small>
              10–300 seconds. Each occurrence receives a saved noise seed;
              retries keep the same recipe.
            </small>
          </label>
        </div>
      )}
      {kind === "ambient" && (
        <label className="field">
          <span>Recurring narration script (optional)</span>
          <textarea
            name="render_script"
            rows={4}
            minLength={15}
            maxLength={3000}
            defaultValue={recipe.script || ""}
            placeholder="An original script used for every scheduled video…"
          />
          <small>Future edits require renewed recipe approval.</small>
        </label>
      )}
      <div className="form-two">
        <label className="field">
          <span>Execution</span>
          {kind === "ambient" ? (
            <>
              <input type="hidden" name="mode" value="live" />
              <p>Live local rendering · connected worker required</p>
            </>
          ) : (
            <select name="mode" defaultValue={r?.mode || "rehearsal"}>
              <option value="rehearsal">Rehearsal · no model calls</option>
              <option value="live">Live · connected worker required</option>
            </select>
          )}
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
            defaultValue={defaultRun}
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
      {kind === "ambient" ? (
        <>
          <label className="checkbox">
            <input type="checkbox" name="render_approved" required />
            <span>
              I approve recurring original videos with this recipe and timing.
              Publication requires separate approval.
            </span>
          </label>
          <p className="inset-note">
            The Ambient editorial queue renders each due video into the private
            library. Account, schedule, studio and workspace pauses apply. A
            failed run holds the next one for review. No model call or automatic
            post is made.
          </p>
        </>
      ) : (
        <p className="inset-note">
          Astra delegates each brief to the account’s studio. This creates
          scripts and editorial packages; it grants no automatic publishing
          approval.
        </p>
      )}
      <Button type="submit" disabled={busy}>
        Save schedule
      </Button>
    </form>
  );
}
