"use client";
import { useRef, useState } from "react";
import { Box, GitBranch, Minus, Plus, Maximize2 } from "lucide-react";
import { projectedPoint, type Agent } from "@/lib/domain";
export default function NetworkGraph({
  agents,
  counts,
  selected,
  onSelect,
}: {
  agents: Agent[];
  counts: Record<string, Record<string, number>>;
  selected: string;
  onSelect: (s: string) => void;
}) {
  const [rotation, setRotation] = useState(-0.08),
    [tilt, setTilt] = useState(0.24),
    [zoom, setZoom] = useState(1),
    [flat, setFlat] = useState(false);
  const drag = useRef<{
    x: number;
    y: number;
    rotation: number;
    tilt: number;
  } | null>(null);
  const points = agents.map((a, index) => {
    const root = index === 0,
      col = (index - 1) % 4,
      row = Math.floor((index - 1) / 4);
    const x = root ? 0 : (col - 1.5) * 205,
      y = root ? -155 : -30 + row * 100,
      z = root ? 0 : col % 2 ? 45 : -45;
    return {
      ...a,
      ...projectedPoint(
        x,
        y,
        flat ? 0 : z,
        flat ? 0 : rotation,
        flat ? 0 : tilt,
        zoom,
      ),
    };
  });
  return (
    <div className="graph-area">
      <div className="graph-toolbar">
        <div className="segmented">
          <button
            className={!flat ? "active" : ""}
            onClick={() => setFlat(false)}
          >
            <Box size={14} /> 3D map
          </button>
          <button
            className={flat ? "active" : ""}
            onClick={() => setFlat(true)}
          >
            <GitBranch size={14} /> Tree
          </button>
        </div>
        <span>Drag to orbit</span>
      </div>
      <svg
        className="network-svg"
        viewBox="0 0 900 520"
        aria-label="Interactive agent delegation tree"
        onPointerDown={(e) => {
          if ((e.target as Element).closest('[role="button"]')) return;
          drag.current = { x: e.clientX, y: e.clientY, rotation, tilt };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (drag.current && !flat) {
            setRotation(
              Math.max(
                -0.7,
                Math.min(
                  0.7,
                  drag.current.rotation + (e.clientX - drag.current.x) * 0.005,
                ),
              ),
            );
            setTilt(
              Math.max(
                -0.3,
                Math.min(
                  0.65,
                  drag.current.tilt + (e.clientY - drag.current.y) * 0.004,
                ),
              ),
            );
          }
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerCancel={() => (drag.current = null)}
      >
        <defs>
          <pattern
            id="grid"
            width="28"
            height="28"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="1" cy="1" r=".7" fill="#34404d" />
          </pattern>
          <radialGradient id="halo">
            <stop stopColor="#b7ef67" stopOpacity=".08" />
            <stop offset="1" stopColor="#b7ef67" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="900" height="520" fill="url(#grid)" />
        <ellipse cx="450" cy="170" rx="220" ry="150" fill="url(#halo)" />
        {points
          .filter((p) => points.some((a) => a.id === p.parent))
          .map((p) => {
            const parent = points.find((a) => a.id === p.parent)!;
            return (
              <g key={p.id}>
                <path
                  d={`M${parent.x},${parent.y + 22} C${parent.x},${(parent.y + p.y) / 2} ${p.x},${(parent.y + p.y) / 2} ${p.x},${p.y - 22}`}
                  stroke={
                    selected === p.id || selected === parent.id
                      ? p.color
                      : "#394551"
                  }
                  strokeWidth={selected === p.id ? 1.6 : 1}
                  fill="none"
                  opacity={p.paused ? 0.35 : 0.8}
                />
                <circle cx={p.x} cy={p.y - 22} r="2" fill={p.color} />
              </g>
            );
          })}
        {[...points]
          .sort((a, b) => b.depth - a.depth)
          .map((p) => {
            const root = p.id === agents[0].id,
              active = selected === p.id,
              running = (counts[p.id]?.running || 0) > 0;
            const w = 170,
              h = root ? 74 : 61;
            return (
              <g
                className="graph-node"
                key={p.id}
                role="button"
                tabIndex={0}
                aria-pressed={active}
                aria-label={`${p.name}, ${p.role}, ${p.paused ? "paused" : "enabled"}`}
                transform={`translate(${p.x},${p.y})`}
                onClick={() => onSelect(p.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(p.id);
                  }
                }}
                opacity={p.paused || p.archived ? 0.55 : 1}
              >
                <rect
                  x={-w / 2}
                  y={-h / 2}
                  width={w}
                  height={h}
                  rx={root ? 12 : 8}
                  fill={active ? "#1c2b24" : root ? "#1a2424" : "#131b24"}
                  stroke={active ? p.color : root ? "#607343" : "#3c4a59"}
                  strokeWidth={active ? 1.8 : 1}
                />
                <defs>
                  <clipPath id={`name-${p.id}`}>
                    <rect x="-72" y="-18" width="144" height="40" />
                  </clipPath>
                </defs>
                {root && (
                  <text
                    x="0"
                    y="-10"
                    fill={p.color}
                    fontSize="12"
                    textAnchor="middle"
                    letterSpacing="2"
                  >
                    {p.id === "astra" ? "✳ ORCHESTRATOR" : "✳ BRANCH"}
                  </text>
                )}
                <text
                  x="0"
                  y={root ? 12 : -2}
                  textAnchor="middle"
                  fill={root ? "#d8f5bc" : "#e0e7ee"}
                  fontSize={root ? 18 : 13}
                  fontWeight={root ? 600 : 500}
                  clipPath={`url(#name-${p.id})`}
                >
                  {p.name.length > (root ? 14 : 18)
                    ? p.name.slice(0, root ? 13 : 17) + "…"
                    : p.name}
                </text>
                {
                  <text
                    x="0"
                    y={root ? 29 : 17}
                    textAnchor="middle"
                    fill="#92a19c"
                    fontSize="11"
                  >
                    {p.archived
                      ? "RETIRED"
                      : root
                        ? p.model.length > 22
                          ? p.model.slice(0, 21) + "…"
                          : p.model
                        : `${p.task_role.toUpperCase()} · ${p.child_count} BELOW`}
                  </text>
                }
                {running && (
                  <circle
                    cx={w / 2 - 10}
                    cy={-h / 2 + 10}
                    r="3"
                    fill="#c6f688"
                    className="pulse"
                  />
                )}
              </g>
            );
          })}
      </svg>
      <div className="graph-controls">
        <button
          aria-label="Zoom out"
          onClick={() => setZoom((z) => Math.max(0.65, z - 0.1))}
        >
          <Minus size={16} />
        </button>
        <span>{Math.round(zoom * 100)}%</span>
        <button
          aria-label="Zoom in"
          onClick={() => setZoom((z) => Math.min(1.25, z + 0.1))}
        >
          <Plus size={16} />
        </button>
        <button
          aria-label="Reset view"
          onClick={() => {
            setRotation(-0.08);
            setTilt(0.24);
            setZoom(1);
          }}
        >
          <Maximize2 size={16} />
        </button>
      </div>
      <div className="graph-id mono">
        BRANCH VIEW
        <br />
        <span>{agents.length - 1} CHILDREN SHOWN</span>
      </div>
    </div>
  );
}
