"use client";
import type { QueryConfig, QueryOptions } from "@/lib/types";
export function defaultQuery(options: QueryOptions): QueryConfig {
  return {
    model: options.models[0],
    prompt_version: options.prompt_versions[0],
    top_k: 5,
    minimum_score: 0,
    agent_mode: false,
  };
}
export function QuerySettings({
  value,
  onChange,
  options,
  disabled = false,
}: {
  value: QueryConfig;
  onChange: (v: QueryConfig) => void;
  options: QueryOptions;
  disabled?: boolean;
}) {
  return (
    <fieldset disabled={disabled} className="query-settings">
      <legend>Query configuration</legend>
      <div className="form-grid">
        <label>
          Generation model
          <select
            value={value.model}
            onChange={(e) => onChange({ ...value, model: e.target.value })}
          >
            {options.models.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
        <label>
          Prompt version
          <select
            value={value.prompt_version}
            onChange={(e) =>
              onChange({ ...value, prompt_version: e.target.value })
            }
          >
            {options.prompt_versions.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label>
          Retrieved chunks (top K)
          <input
            type="number"
            required
            min={1}
            max={options.max_top_k}
            value={value.top_k}
            onChange={(e) =>
              onChange({ ...value, top_k: Number(e.target.value) })
            }
          />
        </label>
        <label>
          Minimum similarity
          <input
            type="number"
            required
            min={-1}
            max={1}
            step={0.05}
            value={value.minimum_score}
            onChange={(e) =>
              onChange({ ...value, minimum_score: Number(e.target.value) })
            }
          />
        </label>
      </div>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={value.agent_mode}
          onChange={(e) => onChange({ ...value, agent_mode: e.target.checked })}
        />
        Enable agent tools
        <span>
          Search, calculator and document metadata · up to{" "}
          {options.max_tool_calls} calls
        </span>
      </label>
    </fieldset>
  );
}
