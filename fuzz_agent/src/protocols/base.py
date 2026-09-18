class ProtocolBase:
    name = "base"

    def build_request(self, **kwargs) -> bytes:
        raise NotImplementedError

    def send_payload(self, payload, host, port) -> bytes:
        raise NotImplementedError

    def parse_response(self, raw) -> dict:
        raise NotImplementedError

    def get_default_port(self) -> int:
        raise NotImplementedError

    def get_func_codes(self) -> list:
        raise NotImplementedError

    def connect(self, host, port, **kwargs) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return False

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures,
                 llm_status=None, stop_event=None):
        raise NotImplementedError