import { createClients as createApiClients } from "./api/transports/http/api";
import type * as ApiDemoModels from "./api/routes/api/demo/models";
import { createClients as createStaticClients } from "./static/transports/http/static";

const apiClients = createApiClients();
const cli = apiClients.demoClient;
const v: ApiDemoModels.ReqAbcQuery = {};


const staticClients = createStaticClients();
const cli2 = staticClients.staticClient;
const v2 = cli2.docJson()
