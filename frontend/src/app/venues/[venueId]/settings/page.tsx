import { redirect } from "next/navigation";

export default async function VenueSettingsRedirectPage({
  params,
}: {
  params: Promise<{ venueId: string }>;
}) {
  const { venueId } = await params;
  redirect(`/venues/${venueId}/settings/cameras`);
}
