import json


def main():
    mean = lambda l: sum(l) / len(l)
    with open("results-window.json") as f:
        window_res = json.load(f)
    with open("results-fence.json") as f:
        fence_res = json.load(f)

    for key in sorted(window_res):
        wind_packets = int(mean([pckt for pckt, secs in window_res[key]]))
        wind_seconds = mean([secs for pckt, secs in window_res[key]])
        fence_packets = int(mean([pckt for pckt, secs in fence_res[key]]))
        fence_seconds = mean([secs for pckt, secs in fence_res[key]])
        print(
            f"| {key}% | {wind_packets} | {fence_packets} | {wind_seconds:.1f} | {fence_seconds:.1f} |"
        )


if __name__ == "__main__":
    main()
