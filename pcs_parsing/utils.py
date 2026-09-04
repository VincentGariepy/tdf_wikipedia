import json

def print_results(results: dict, file_path: str = None):
    print_results = """
    ### Stage General Info
    {stage_general_info}

    ### Stage Results
    {stage_results}

    ### GC Results
    {gc_results}

    ### Points Results
    {points_results}

    ### Teams Results
    {teams_results}
    """.format(
        stage_general_info=json.dumps(results['stage_general_info'], indent=4, ensure_ascii=False),
        stage_results=results['stage_results'].to_markdown(index=False),
        gc_results=results['gc_results'].to_markdown(index=False),
        points_results=results['points_results'].to_markdown(index=False),
        teams_results=results['teams_results'].to_markdown(index=False),
    )

    if file_path:
        with open("results_example_stage2_1947.txt", "w", encoding="utf-8") as f:
            f.write(print_results)
        return
    else:
        return print_results