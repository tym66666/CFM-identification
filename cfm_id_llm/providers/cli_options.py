"""Explicit opt-in transport controls shared by A0 and NBIB; no credentials."""


def add_chat_arguments(parser):
    parser.add_argument('--timeout', type=float, default=60.0,
                        help='Socket operation timeout in seconds; not a total request deadline')
    parser.add_argument('--stream', action='store_true', help='Read bounded Chat Completions SSE')
    parser.add_argument('--max-stream-seconds', type=float, default=300.0,
                        help='Elapsed stream limit checked between reads')
    budget = parser.add_mutually_exclusive_group()
    budget.add_argument('--max-completion-tokens', type=int)
    budget.add_argument('--max-tokens', type=int,
                        help='Explicit max_tokens parameter for compatible providers such as DeepSeek')
    parser.add_argument('--require-finish-reason', action='store_true',
                        help='Also reject nonstream responses without a normal finish_reason')
    parser.add_argument('--json-mode', choices=('on', 'off'), default='on',
                        help='Send response_format=json_object (on); off keeps strict local JSON validation')
    parser.add_argument('--thinking', choices=('default', 'enabled', 'disabled'), default='default',
                        help='Explicit provider-specific thinking parameter; default sends none')


def chat_options(args):
    return dict(timeout=args.timeout, stream=args.stream,
                max_stream_seconds=args.max_stream_seconds,
                max_completion_tokens=args.max_completion_tokens,
                max_tokens=args.max_tokens,
                require_finish_reason=args.require_finish_reason,
                json_mode=args.json_mode == 'on',
                thinking=None if args.thinking == 'default' else args.thinking)
