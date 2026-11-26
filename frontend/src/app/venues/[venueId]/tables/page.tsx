import { redirect } from "next/navigation";

export default async function VenueTablesRedirectPage({
  params,
}: {
  params: Promise<{ venueId: string }>;
}) {
  const { venueId } = await params;
  redirect(`/venues/${venueId}/floor`);
}
