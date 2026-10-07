import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { shortDay, verdictLabel } from "./analyticsFormat";

/**
 * The charts behind the analytics summary. Every series here is read straight
 * from the response the API computed -- the page never re-derives a rate or a
 * count locally, so what a bar looks like and what a card says cannot drift.
 */

const GRID = "#25304a";
const AXIS = { fill: "#8d9ab5", fontSize: 12 };
const TOOLTIP = {
  background: "#151d32",
  border: "1px solid #2b3857",
  borderRadius: 12,
  color: "#f4f7ff",
};
const LEGEND = { color: "#8d9ab5", fontSize: 12 };

const SOLVED = "#3cc9b0";
const ATTEMPTED = "#7c6cff";
const UNTOUCHED = "#33415f";

/** Palette for verdict slices; distinct hues so a wedge is tellable at a glance. */
const VERDICT_COLORS = ["#3cc9b0", "#7c6cff", "#f4bd6a", "#f2607e", "#4ea8ff", "#9b8cff", "#65e3ca", "#e0a458", "#8d9ab5"];

export function DifficultyChart({ rows }) {
  const data = rows.map((row) => ({
    difficulty: row.difficulty,
    solved: row.solved,
    attempted: row.attempted,
    not_started: row.not_started,
  }));

  return (
    <div className="chart-wrap analytics-chart">
      <ResponsiveContainer height={300} width="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis axisLine={false} dataKey="difficulty" tick={AXIS} tickLine={false} />
          <YAxis allowDecimals={false} axisLine={false} tick={AXIS} tickLine={false} />
          <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "rgba(124,108,255,0.1)" }} />
          <Legend wrapperStyle={LEGEND} />
          <Bar
            dataKey="not_started"
            fill={UNTOUCHED}
            isAnimationActive={false}
            name="Not started"
            stackId="mastery"
          />
          <Bar
            dataKey="attempted"
            fill={ATTEMPTED}
            isAnimationActive={false}
            name="Attempted"
            stackId="mastery"
          />
          <Bar
            dataKey="solved"
            fill={SOLVED}
            isAnimationActive={false}
            name="Solved"
            radius={[6, 6, 0, 0]}
            stackId="mastery"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TopicChart({ rows }) {
  const data = rows.map((row) => ({
    topic: row.topic,
    solved: row.solved,
    remaining: Math.max(row.total - row.solved, 0),
  }));

  return (
    <div className="chart-wrap analytics-chart">
      <ResponsiveContainer height={Math.max(240, data.length * 36)} width="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, left: 4, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke={GRID} strokeDasharray="3 3" />
          <XAxis allowDecimals={false} axisLine={false} tick={AXIS} tickLine={false} type="number" />
          <YAxis
            axisLine={false}
            dataKey="topic"
            tick={AXIS}
            tickLine={false}
            type="category"
            width={132}
          />
          <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "rgba(124,108,255,0.1)" }} />
          <Legend wrapperStyle={LEGEND} />
          <Bar
            dataKey="remaining"
            fill={UNTOUCHED}
            isAnimationActive={false}
            name="Remaining"
            stackId="topics"
          />
          <Bar
            dataKey="solved"
            fill={SOLVED}
            isAnimationActive={false}
            name="Solved"
            radius={[0, 6, 6, 0]}
            stackId="topics"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * The verdict distribution as a donut plus a labelled list. The list is not
 * decoration: a wedge alone cannot say "3 of 4", and every number here has to
 * stay readable without colour vision or a hover.
 */
export function VerdictChart({ rows }) {
  const data = rows.map((row, index) => ({
    name: verdictLabel(row.status),
    status: row.status,
    value: row.count,
    percentage: row.percentage,
    color: VERDICT_COLORS[index % VERDICT_COLORS.length],
  }));

  return (
    <div className="verdict-block">
      <div className="chart-wrap analytics-chart">
        <ResponsiveContainer height={280} width="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              innerRadius={58}
              isAnimationActive={false}
              nameKey="name"
              outerRadius={100}
              paddingAngle={2}
            >
              {data.map((entry) => (
                <Cell fill={entry.color} key={entry.status} />
              ))}
            </Pie>
            <Legend wrapperStyle={LEGEND} />
            <Tooltip contentStyle={TOOLTIP} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="verdict-list">
        {data.map((entry) => (
          <li key={entry.status}>
            <span className="verdict-dot" style={{ background: entry.color }} />
            <strong>{entry.name}</strong>
            <span>
              {entry.value} {entry.value === 1 ? "submission" : "submissions"}
            </span>
            <span>{entry.percentage}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Submissions and solves per day over the window the response says it covers.
 * The dates are pre-shortened here rather than formatted by a tick callback,
 * so the axis and the tooltip always label the same stored day.
 */
export function ActivityChart({ days }) {
  const data = days.map((day) => ({
    date: shortDay(day.date),
    submissions: day.submissions,
    solves: day.solves,
  }));
  const interval = Math.max(0, Math.ceil(data.length / 6) - 1);

  return (
    <div className="chart-wrap analytics-chart">
      <ResponsiveContainer height={300} width="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="activitySubmissions" x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor={ATTEMPTED} stopOpacity={0.45} />
              <stop offset="95%" stopColor={ATTEMPTED} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="activitySolves" x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor={SOLVED} stopOpacity={0.45} />
              <stop offset="95%" stopColor={SOLVED} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis axisLine={false} dataKey="date" interval={interval} tick={AXIS} tickLine={false} />
          <YAxis allowDecimals={false} axisLine={false} tick={AXIS} tickLine={false} />
          <Tooltip contentStyle={TOOLTIP} />
          <Legend wrapperStyle={LEGEND} />
          <Area
            dataKey="solves"
            fill="url(#activitySolves)"
            isAnimationActive={false}
            name="Solved"
            stroke={SOLVED}
          />
          <Area
            dataKey="submissions"
            fill="url(#activitySubmissions)"
            isAnimationActive={false}
            name="Submissions"
            stroke={ATTEMPTED}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Completed interviews in completion order, score out of 100. */
export function InterviewScoreChart({ scores }) {
  const data = scores.map((point, index) => ({
    session: `#${index + 1}`,
    score: point.score,
  }));

  return (
    <div className="chart-wrap analytics-chart">
      <ResponsiveContainer height={240} width="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis axisLine={false} dataKey="session" tick={AXIS} tickLine={false} />
          <YAxis allowDecimals={false} axisLine={false} domain={[0, 100]} tick={AXIS} tickLine={false} />
          <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "rgba(124,108,255,0.1)" }} />
          <Bar
            dataKey="score"
            fill={ATTEMPTED}
            isAnimationActive={false}
            name="Score"
            radius={[6, 6, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
