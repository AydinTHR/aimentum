import { api } from "../api/client";
import { Card, ErrorNote, SectionLabel, Spinner } from "../components/ui";
import { formatDateShort } from "../lib/time";
import { useApi } from "../lib/useApi";

/** The Sunday letters: one honest look back per week, newest first. */
export function RetrosScreen() {
  const retros = useApi(api.retros);

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Retros</h1>
        <p className="mt-1 text-sm text-zinc-400">
          A look back at every week, written Sunday evening.
        </p>
      </header>

      {retros.loading && !retros.data && <Spinner label="Loading retros" />}
      {retros.error && !retros.data && <ErrorNote>{retros.error}</ErrorNote>}
      {retros.data?.length === 0 && (
        <p className="text-sm text-zinc-500">
          Nothing here yet. The first retro lands Sunday evening.
        </p>
      )}

      {(retros.data ?? []).map((retro) => (
        <Card key={retro.id}>
          <SectionLabel>Week of {formatDateShort(retro.week_start)}</SectionLabel>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-zinc-200">
            {retro.body}
          </p>
        </Card>
      ))}
    </div>
  );
}
