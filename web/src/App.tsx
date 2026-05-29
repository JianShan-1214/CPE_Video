import { Route, Routes } from "react-router-dom";
import { GenerateJob } from "@/pages/GenerateJob";
import { ImportJob } from "@/pages/ImportJob";
import { JobEdit } from "@/pages/JobEdit";
import { JobList } from "@/pages/JobList";
import { NewJob } from "@/pages/NewJob";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<JobList />} />
      <Route path="/new" element={<NewJob />} />
      <Route path="/new/generate" element={<GenerateJob />} />
      <Route path="/new/import" element={<ImportJob />} />
      <Route path="/jobs/:id/edit" element={<JobEdit />} />
    </Routes>
  );
}
