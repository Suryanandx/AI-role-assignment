import { request, gql } from "graphql-request";

const graphqlUrl =
  process.env.NEXT_PUBLIC_GRAPHQL_URL ?? "http://localhost:8000/graphql";

export type JobResult = {
  id: string;
  status: string;
  topic: string;
} | null;

const JobQuery = gql`
  query Job($id: ID!) {
    job(id: $id) {
      id
      status
      topic
    }
  }
`;

export async function getJob(id: string): Promise<JobResult> {
  const data = await request<{ job: JobResult }>(graphqlUrl, JobQuery, {
    id,
  });
  return data.job;
}
