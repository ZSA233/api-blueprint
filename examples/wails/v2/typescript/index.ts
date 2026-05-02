import { Demo } from './api';

const client = new Demo.DemoClient();
const bridge = client.connectWs();
void bridge.ready;

const request: Demo.ReqAbcQuery = {};
void client.abc({ query: request });
