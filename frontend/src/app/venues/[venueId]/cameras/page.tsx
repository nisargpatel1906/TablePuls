import { redirect } from "next/navigation";

export default async function VenueCamerasRedirectPage({
  params,
}: {
  params: Promise<{ venueId: string }>;
}) {
  const { venueId } = await params;
  redirect(`/venues/${venueId}/cameras/live`);
}
