import { fetchTeams } from '../../lib/data';
import ScoutingReportForm from './ScoutingReportForm';

export default async function ScoutingPage() {
  const { teams } = await fetchTeams();

  return (
    <main>
      <ScoutingReportForm teams={teams} />
    </main>
  );
}
