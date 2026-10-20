"""Extend the existing no-restart API adapter with exact prompt admission."""
import sys

from protocol import admit_prompt


def install(server):
    original = server.Service.prepare

    def prepare(self, messages, tools, kwargs, max_new=None, force=None, req=None, cancel=None):
        if tools or force or kwargs.get('enable_thinking') is not False:
            raise ValueError('MANUAL_TEXT_WITHOUT_THINKING_ONLY')
        # Encode using the actual server tokenizer/template, including literal
        # handling and history. This executes before Service.run/inference.
        ids = self.encode_prompt(messages, tools, kwargs)
        admit_prompt(ids, max_new)
        result = original(self, messages, tools, kwargs, max_new, force, req, cancel)
        if result[0] != ids or result[2] != max_new:
            raise ValueError('MANUAL_PROMPT_REWRITTEN')
        return result

    server.Service.prepare = prepare


if __name__ == '__main__':
    sys.path[:0] = ['/source', '/source/tools', '/runtime/site']
    from serve import server
    install(server)
    import api_wrapper
    api_wrapper.main()
