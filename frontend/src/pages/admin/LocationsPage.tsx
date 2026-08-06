import { TitleResourceManager } from "../../components/admin/TitleResourceManager";
import { createLocation, fetchLocations, updateLocation } from "../../api/locations";

export function LocationsPage() {
  return (
    <TitleResourceManager
      resourceName="Location"
      fetchAll={fetchLocations}
      create={createLocation}
      update={updateLocation}
      supportsActivation
    />
  );
}
