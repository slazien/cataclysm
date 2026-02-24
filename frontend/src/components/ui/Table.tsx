"use client";

interface TableColumn<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  rowKey: (row: T) => string | number;
  className?: string;
  emptyMessage?: string;
}

export default function Table<T>({
  columns,
  data,
  rowKey,
  className = "",
  emptyMessage = "No data",
}: TableProps<T>) {
  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-[var(--text-muted)]">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-color)]">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)] ${col.className ?? ""}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={rowKey(row)}
              className={`border-b border-[var(--border-color)] ${
                i % 2 === 0
                  ? "bg-[var(--bg-secondary)]"
                  : "bg-[var(--bg-primary)]"
              }`}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-3 py-2 text-[var(--text-primary)] ${col.className ?? ""}`}
                >
                  {col.render
                    ? col.render(row)
                    : String((row as Record<string, unknown>)[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
