import multiprocessing
import shutil
from enum import Enum
from pathlib import Path
from typing import List, Optional
import re

import docker
import matplotlib.pyplot as plt
import numpy as np
import typer
from rich import print


# Definition of enumerated classes.
class Database(str, Enum):
    DREAM3 = "DREAM3"
    DREAM4 = "DREAM4"
    DREAM5 = "DREAM5"
    SynTReN = "SynTReN"
    Rogers = "Rogers"
    GeneNetWeaver = "GeneNetWeaver"
    IRMA = "IRMA"


class EvalDatabase(str, Enum):
    DREAM3 = "DREAM3"
    DREAM4 = "DREAM4"
    DREAM5 = "DREAM5"


class Technique(str, Enum):
    ARACNE = "ARACNE"
    BC3NET = "BC3NET"
    C3NET = "C3NET"
    CLR = "CLR"
    GENIE3_RF = "GENIE3_RF"
    GENIE3_GBM = "GENIE3_GBM"
    GENIE3_ET = "GENIE3_ET"
    MRNET = "MRNET"
    MRNETB = "MRNETB"
    PCIT = "PCIT"
    TIGRESS = "TIGRESS"
    KBOOST = "KBOOST"


class CutOffCriteriaOnlyConf(str, Enum):
    MinConfidence = "MinConfidence"
    MaxNumLinksBestConf = "MaxNumLinksBestConf"


class CutOffCriteria(str, Enum):
    MinConfidence = "MinConfidence"
    MaxNumLinksBestConf = "MaxNumLinksBestConf"
    MinConfDist = "MinConfDist"


class Crossover(str, Enum):
    SBXCrossover = "SBXCrossover"
    BLXAlphaCrossover = "BLXAlphaCrossover"
    DifferentialEvolutionCrossover = "DifferentialEvolutionCrossover"
    NPointCrossover = "NPointCrossover"
    NullCrossover = "NullCrossover"
    WholeArithmeticCrossover = "WholeArithmeticCrossover"


class Mutation(str, Enum):
    PolynomialMutation = "PolynomialMutation"
    CDGMutation = "CDGMutation"
    GroupedAndLinkedPolynomialMutation = "GroupedAndLinkedPolynomialMutation"
    GroupedPolynomialMutation = "GroupedPolynomialMutation"
    LinkedPolynomialMutation = "LinkedPolynomialMutation"
    NonUniformMutation = "NonUniformMutation"
    NullMutation = "NullMutation"
    SimpleRandomMutation = "SimpleRandomMutation"
    UniformMutation = "UniformMutation"


class Repairer(str, Enum):
    StandardizationRepairer = "StandardizationRepairer"
    GreedyRepair = "GreedyRepair"


class Challenge(str, Enum):
    D3C4 = "D3C4"
    D4C2 = "D4C2"
    D5C4 = "D5C4"


class NodesDistribution(str, Enum):
    Spring = "Spring"
    Circular = "Circular"
    Kamada_kawai = "Kamada_kawai"


class Mode(str, Enum):
    Static2D = "Static2D"
    Interactive3D = "Interactive3D"
    Both = "Both"


class Algorithm(str, Enum):
    GA = "GA"
    NSGAII = "NSGAII"
    SMPSO = "SMPSO"
    MOEAD = "MOEAD"
    GDE3 = "GDE3"


# Function for obtaining the list of genes from lists of confidence levels.
def get_gene_names_from_conf_list(conf_list):
    gene_list = set()
    with open(conf_list, "r") as f:
        for row in f:
            row_list = row.split(",")
            gene_list.add(row_list[0])
            gene_list.add(row_list[1])
    f.close()
    return gene_list


# Function for obtaining the list of genes from expression file.
def get_gene_names_from_expression_file(expression_file):
    with open(expression_file, "r") as f:
        gene_list = [row.split(",")[0].replace('"', "") for row in f]
        if gene_list[0] == "":
            del gene_list[0]
    f.close()
    return gene_list


# Function to wait and close container in execution
def wait_and_close_container(container):
    # Wait for the container to run and get logs
    container.wait()
    logs = container.logs()

    # Stop and remove the container
    container.stop()
    container.remove(v=True)

    # Return logs
    return logs.decode("utf-8")


# Function to obtain the definition of a volume given a folder
def get_volume(folder):
    return {
        Path(f"./{folder}/").absolute(): {
            "bind": f"/usr/local/src/{folder}",
            "mode": "rw",
        }
    }


# Applications for the definition of Typer commands and subcommands.
app = typer.Typer(rich_markup_mode="rich")

## Evaluation
evaluate_app = typer.Typer()
app.add_typer(
    evaluate_app,
    name="evaluate",
    help="Evaluate the accuracy of the inferred network with respect to its gold standard.",
    rich_help_panel="Additional commands",
)

### Dream challenges
dream_prediction_app = typer.Typer()
evaluate_app.add_typer(
    dream_prediction_app,
    name="dream-prediction",
    help="Evaluate the accuracy with which networks belonging to the DREAM challenges are predicted.",
)

### Generic challenges
generic_prediction_app = typer.Typer()
evaluate_app.add_typer(
    generic_prediction_app,
    name="generic-prediction",
    help="Evaluate the accuracy with which any generic network has been predicted with respect to a given gold standard. To do so, it approaches the case as a binary classification problem between 0 and 1.",
)

## Data extraction
extract_data_app = typer.Typer()
app.add_typer(
    extract_data_app,
    name="extract-data",
    help="Extract data from different simulators and known challenges. These include DREAM3, DREAM4, DREAM5, SynTReN, Rogers, GeneNetWeaver and IRMA.",
    rich_help_panel="Additional commands",
)

# Activate docker client.
client = docker.from_env()

# List available images on the current device.
available_images = [
    i.tags[0].split(":")[0] if len(i.tags) > 0 else None for i in client.images.list()
]


# Command for expression data extraction.
@extract_data_app.command()
def expression_data(
    database: Optional[List[Database]] = typer.Option(
        ..., case_sensitive=False, help="Databases for downloading expression data."
    ),
    output_dir: Path = typer.Option(
        Path("./input_data"), help="Path to the output folder."
    ),
    username: str = typer.Option(
        None,
        help="Synapse account username. Only necessary when selecting DREAM3 or DREAM5.",
    ),
    password: str = typer.Option(
        None,
        help="Synapse account password. Only necessary when selecting DREAM3 or DREAM5.",
    ),
):
    """
    Download differential expression data from various databases such as DREAM3, DREAM4, DREAM5, SynTReN, Rogers, GeneNetWeaver and IRMA.
    """

    # Demand the proportion of credentials if necessary.
    if (Database.DREAM3 in database or Database.DREAM5 in database) and (
        not username or not password
    ):
        print(
            "You must enter your Synapse credentials in order to download some of the selected data."
        )
        raise typer.Exit()

    # Scroll through the list of databases specified by the user to extract data from each of them.
    for db in database:

        # Create the output folder
        Path(f"./{output_dir}/{db}/EXP/").mkdir(exist_ok=True, parents=True)

        # Report information to the user
        print(f"\n Extracting expression data from {db}")

        # Execute the corresponding image according to the database.
        if db == "DREAM3":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream3"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"--category ExpressionData --output-folder {output_dir} --username {username} --password {password}"

        elif db == "DREAM4":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream4-expgs"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"ExpressionData {output_dir}"

        elif db == "DREAM5":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream5"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"--category ExpressionData --output-folder {output_dir} --username {username} --password {password}"

        elif db == "IRMA":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_irma"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"ExpressionData {output_dir}"

        else:

            # Define docker image
            image = "adriansegura99/geneci_extract-data_grndata"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"{db} ExpressionData {output_dir}"

        # Run container
        container = client.containers.run(
            image=image,
            volumes=get_volume(output_dir),
            command=command,
            detach=True,
            tty=True,
        )

        # Wait, stop and remove the container. Then print reported logs
        logs = wait_and_close_container(container)
        print(logs)


# Command to extract gold standards
@extract_data_app.command()
def gold_standard(
    database: Optional[List[Database]] = typer.Option(
        ..., case_sensitive=False, help="Databases for downloading gold standards."
    ),
    output_dir: Path = typer.Option(
        Path("./input_data"), help="Path to the output folder."
    ),
    username: str = typer.Option(
        None,
        help="Synapse account username. Only necessary when selecting DREAM3 or DREAM5.",
    ),
    password: str = typer.Option(
        None,
        help="Synapse account password. Only necessary when selecting DREAM3 or DREAM5.",
    ),
):
    """
    Download gold standards from various databases such as DREAM3, DREAM4, DREAM5, SynTReN, Rogers, GeneNetWeaver and IRMA.
    """

    # Demand the proportion of credentials if necessary.
    if (Database.DREAM3 in database or Database.DREAM5 in database) and (
        not username or not password
    ):
        print(
            "You must enter your Synapse credentials in order to download some of the selected data."
        )
        raise typer.Exit()

    # Scroll through the list of databases specified by the user to extract data from each of them.
    for db in database:

        # Create the output folder
        Path(f"./{output_dir}/{db}/GS/").mkdir(exist_ok=True, parents=True)

        # Report information to the user
        print(f"\n Extracting gold standards from {db}")

        # Execute the corresponding image according to the database.
        if db == "DREAM3":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream3"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"--category GoldStandard --output-folder {output_dir} --username {username} --password {password}"

        elif db == "DREAM4":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream4-expgs"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"GoldStandard {output_dir}"

        elif db == "DREAM5":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream5"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"--category GoldStandard --output-folder {output_dir} --username {username} --password {password}"

        elif db == "IRMA":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_irma"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"GoldStandard {output_dir}"

        else:

            # Define docker image
            image = "adriansegura99/geneci_extract-data_grndata"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"{db} GoldStandard {output_dir}"

        # Run container
        container = client.containers.run(
            image=image,
            volumes=get_volume(output_dir),
            command=command,
            detach=True,
            tty=True,
        )

        # Wait, stop and remove the container. Then print reported logs
        logs = wait_and_close_container(container)
        print(logs)


# Command to extract evaluation data
@extract_data_app.command()
def evaluation_data(
    database: Optional[List[EvalDatabase]] = typer.Option(
        ..., case_sensitive=False, help="Databases for downloading evaluation data."
    ),
    output_dir: Path = typer.Option(
        Path("./input_data"), help="Path to the output folder."
    ),
    username: str = typer.Option(..., help="Synapse account username."),
    password: str = typer.Option(..., help="Synapse account password."),
):
    """
    Download evaluation data from various DREAM challenges.
    """

    # Scroll through the list of databases specified by the user to extract data from each of them.
    for db in database:

        # Create the output folder
        Path(f"./{output_dir}/{db}/EVAL/").mkdir(exist_ok=True, parents=True)

        # Report information to the user
        print(f"\n Extracting evaluation data from {db}")

        # Execute the corresponding image according to the database.
        if db == "DREAM3":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream3"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"--category EvaluationData --output-folder {output_dir} --username {username} --password {password}"

        elif db == "DREAM4":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream4-eval"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"--category EvaluationData --output-folder {output_dir} --username {username} --password {password}"

        elif db == "DREAM5":

            # Define docker image
            image = "adriansegura99/geneci_extract-data_dream5"

            # In case it is not available on the device, it is downloaded from the repository.
            if not image in available_images:
                print("Downloading docker image ...")
                client.images.pull(repository=image)

            # Construct the command based on the parameters entered by the user
            command = f"--category EvaluationData --output-folder {output_dir} --username {username} --password {password}"

        # Run container
        container = client.containers.run(
            image=image,
            volumes=get_volume(output_dir),
            command=command,
            detach=True,
            tty=True,
        )

        # Wait, stop and remove the container. Then print reported logs
        logs = wait_and_close_container(container)
        print(logs)


# Command for inferring networks by applying individual techniques.
@app.command(rich_help_panel="Commands for two-step main execution")
def infer_network(
    expression_data: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        help="Path to the CSV file with the expression data. Genes are distributed in rows and experimental conditions (time series) in columns.",
    ),
    technique: Optional[List[Technique]] = typer.Option(
        ..., case_sensitive=False, help="Inference techniques to be performed."
    ),
    output_dir: Path = typer.Option(
        Path("./inferred_networks"), help="Path to the output folder."
    ),
):
    """
    Infer gene regulatory networks from expression data. Several techniques are available: ARACNE, BC3NET, C3NET, CLR, GENIE3, MRNET, MRNET, MRNETB and PCIT.
    """

    # Create the output folder.
    Path(f"./{output_dir}/{expression_data.stem}/lists/").mkdir(
        exist_ok=True, parents=True
    )

    # Temporarily copy the input files to the same folder in order to facilitate the container volume.
    tmp_exp_dir = f"./{output_dir}/{expression_data.name}"
    shutil.copyfile(expression_data, tmp_exp_dir)

    # The different images corresponding to the inference techniques are run in parallel.
    containers = list()
    for tec in technique:

        # Report information to the user.
        print(f"\n Infer network from {expression_data} with {tec}")

        # The image is selected according to the chosen technique.
        if tec == "GENIE3_RF":
            image = f"adriansegura99/geneci_infer-network_genie3"
            variant = "RF"
        elif tec == "GENIE3_GBM":
            image = f"adriansegura99/geneci_infer-network_genie3"
            variant = "GBM"
        elif tec == "GENIE3_ET":
            image = f"adriansegura99/geneci_infer-network_genie3"
            variant = "ET"
        else:
            image = f"adriansegura99/geneci_infer-network_{tec.lower()}"
            variant = None

        # In case it is not available on the device, it is downloaded from the repository.
        if not image in available_images:
            print("Downloading docker image ...")
            client.images.pull(repository=image)

        # The image is executed with the parameters set by the user.
        container = client.containers.run(
            image=image,
            volumes=get_volume(output_dir),
            command=f"{tmp_exp_dir} {output_dir} {variant}",
            detach=True,
            tty=True,
        )

        # The container is added to the list so that the following can be executed
        containers.append(container)

    # For each container, we wait for it to finish its execution, stop and delete it.
    for container in containers:
        # Wait, stop and remove the container. Then print reported logs
        logs = wait_and_close_container(container)
        print(logs)

    # The initially copied input files are deleted.
    Path(tmp_exp_dir).unlink()

    # An additional file is created with the list of genes for the subsequent optimization process.
    gene_names = f"./{output_dir}/{expression_data.stem}/gene_names.txt"

    # If it doens't exist ...
    if not Path(gene_names).is_file():
        # Get gene names from expression file
        gene_list = get_gene_names_from_expression_file(expression_data)

        # Write gene names to default file
        with open(gene_names, "w") as f:
            f.write(",".join(gene_list))


# Command for network binarization
@app.command(rich_help_panel="Additional commands")
def apply_cut(
    confidence_list: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        help="Path to the CSV file with the list of trusted values.",
    ),
    gene_names: Path = typer.Option(
        None,
        exists=True,
        file_okay=True,
        help="Path to the TXT file with the name of the contemplated genes separated by comma and without space. If not specified, only the genes specified in the list of trusts will be considered.",
    ),
    cut_off_criteria: CutOffCriteriaOnlyConf = typer.Option(
        ...,
        case_sensitive=False,
        help="Criteria for determining which links will be part of the final binary matrix.",
    ),
    cut_off_value: float = typer.Option(
        ...,
        help="Numeric value associated with the selected criterion. Ex: MinConfidence = 0.5, MaxNumLinksBestConf = 10",
    ),
    output_file: Path = typer.Option(
        "<<conf_list_path>>/../networks/<<conf_list_name>>.csv",
        help="Path to the output CSV file that will contain the binary matrix resulting from the cutting operation.",
    ),
):
    """
    Converts a list of confidence values into a binary matrix that represents the final gene network.
    """

    # Report information to the user.
    print(
        f"Apply cut to {confidence_list} with {cut_off_criteria} and value {cut_off_value}"
    )

    # A temporary folder is created and the list of input confidences is copied.
    Path("tmp").mkdir(exist_ok=True, parents=True)
    tmp_confidence_list_dir = f"tmp/{Path(confidence_list).name}"
    shutil.copyfile(confidence_list, tmp_confidence_list_dir)

    # Define default temp path to gene names list
    tmp_gene_names_dir = "tmp/gene_names.txt"

    # If a gene list is provided it is copied to the temporary directory
    if gene_names:
        shutil.copyfile(gene_names, tmp_gene_names_dir)

    # Or else it is created from the trusted list.
    else:
        # Get gene names from confidence list file
        gene_list = get_gene_names_from_conf_list(confidence_list)

        # Write gene names to default file
        with open(tmp_gene_names_dir, "w") as f:
            f.write(",".join(sorted(gene_list)))

    # The output file is defined and the necessary folders of its path are created.
    if str(output_file) == "<<conf_list_path>>/../networks/<<conf_list_name>>.csv":
        output_file = Path(
            f"{Path(confidence_list).parents[1]}/networks/{Path(confidence_list).name}"
        )
    output_file.parent.mkdir(exist_ok=True, parents=True)

    # Define docker image
    image = "adriansegura99/geneci_apply-cut"

    # In case it is not available on the device, it is downloaded from the repository.
    if not image in available_images:
        print("Downloading docker image ...")
        client.images.pull(repository=image)

    # The image is executed with the parameters set by the user.
    container = client.containers.run(
        image=image,
        volumes=get_volume("tmp"),
        command=f"{tmp_confidence_list_dir} {tmp_gene_names_dir} tmp/{output_file} {cut_off_criteria} {cut_off_value}",
        detach=True,
        tty=True,
    )

    # Wait, stop and remove the container. Then print reported logs
    logs = wait_and_close_container(container)
    print(logs)

    # Copy the output file from the temporary folder to the final one and delete the temporary one.
    shutil.copyfile(f"tmp/{output_file}", output_file)
    shutil.rmtree("tmp")


# Command to optimize the ensemble of techniques
@app.command(rich_help_panel="Commands for two-step main execution")
def optimize_ensemble(
    confidence_list: Optional[List[str]] = typer.Option(
        ...,
        help="Paths of the CSV files with the confidence lists to be agreed upon.",
        rich_help_panel="Input data",
    ),
    gene_names: Path = typer.Option(
        None,
        exists=True,
        file_okay=True,
        help="Path to the TXT file with the name of the contemplated genes separated by comma and without space. If not specified, only the genes specified in the lists of trusts will be considered.",
        rich_help_panel="Input data",
    ),
    time_series: Path = typer.Option(
        None,
        exists=True,
        file_okay=True,
        help="Path to the CSV file with the time series from which the individual gene networks have been inferred. This parameter is only necessary in case of specifying the fitness function Loyalty.",
        rich_help_panel="Input data",
    ),
    crossover: Crossover = typer.Option(
        "SBXCrossover", help="Crossover operator", rich_help_panel="Crossover"
    ),
    crossover_probability: float = typer.Option(
        0.9, help="Crossover probability", rich_help_panel="Crossover"
    ),
    mutation: Mutation = typer.Option(
        "PolynomialMutation", help="Mutation operator", rich_help_panel="Mutation"
    ),
    mutation_probability: float = typer.Option(
        -1,
        help="Mutation probability. [default: 1/len(files)]",
        show_default=False,
        rich_help_panel="Mutation",
    ),
    repairer: Repairer = typer.Option(
        "StandardizationRepairer",
        help="Solution repairer to keep the sum of weights equal to 1",
        rich_help_panel="Repairer",
    ),
    population_size: int = typer.Option(
        100, help="Population size", rich_help_panel="Diversity and depth"
    ),
    num_evaluations: int = typer.Option(
        25000, help="Number of evaluations", rich_help_panel="Diversity and depth"
    ),
    cut_off_criteria: CutOffCriteria = typer.Option(
        "MinConfDist",
        case_sensitive=False,
        help="Criteria for determining which links will be part of the final binary matrix.",
        rich_help_panel="Cut-Off",
    ),
    cut_off_value: float = typer.Option(
        0.5,
        help="Numeric value associated with the selected criterion. Ex: MinConfidence = 0.5, MaxNumLinksBestConf = 10, MinConfDist = 0.2",
        rich_help_panel="Cut-Off",
    ),
    function: Optional[List[str]] = typer.Option(
        ["Quality", "Topology"],
        help="A mathematical expression that defines a particular fitness function based on the weighted sum of several independent terms. Available terms: Quality, Topology and Loyalty.",
        rich_help_panel="Fitness",
    ),
    algorithm: Algorithm = typer.Option(
        "NSGAII",
        help="Evolutionary algorithm to be used during the optimization process. All are intended for a multi-objective approach with the exception of the genetic algorithm (GA).",
        rich_help_panel="Orchestration",
    ),
    threads: int = typer.Option(
        multiprocessing.cpu_count(),
        help="Number of threads to be used during parallelization. By default, the maximum number of threads available in the system is used.",
        rich_help_panel="Orchestration",
    ),
    plot_evolution: bool = typer.Option(
        False,
        help="Indicate if you want to represent the evolution of the fitness value.",
        rich_help_panel="Graphics",
    ),
    output_dir: Path = typer.Option(
        "<<conf_list_path>>/../ea_consensus",
        help="Path to the output folder.",
        rich_help_panel="Output",
    ),
):
    """
    Analyzes several trust lists and builds a consensus network by applying an evolutionary algorithm
    """

    # Report information to the user.
    print(f"\n Optimize ensemble for {confidence_list}")

    # If the number of trusted lists is less than two, an error is sent
    if len(confidence_list) < 2:
        print(
            "[bold red]Error:[/bold red] Insufficient number of confidence lists provided"
        )
        raise typer.Abort()

    # Create the string representing the set of fitness functions to be checked in the input to the evolutionary algorithm
    functions = ";".join(function)

    # If the mutation probability is the one established by default, the optimal value is chosen
    if mutation_probability == -1:
        mutation_probability = 1 / len(confidence_list)

    # The temporary folder is created
    Path("tmp/lists").mkdir(exist_ok=True, parents=True)

    # Input trust lists are copied
    for file in confidence_list:
        shutil.copyfile(file, f"tmp/lists/{Path(file).name}")

    # Define default temp path to gene names list
    tmp_gene_names_dir = "tmp/gene_names.txt"

    # If a gene list is provided it is copied to the temporary directory
    if gene_names:
        shutil.copyfile(gene_names, tmp_gene_names_dir)

    # Or else it is created from the trusted list.
    else:

        # Create an empty set to later store the name of the genes
        gene_list = set()

        # For each file provided in the input, the genes contained in the file are read and added to the set
        for file in confidence_list:
            gene_list.update(get_gene_names_from_conf_list(file))

        # Write gene names to default file
        with open(tmp_gene_names_dir, "w") as f:
            f.write(",".join(sorted(gene_list)))

    # Copy the file with the time series if specified
    tmp_time_series_dir = "tmp/time_series.csv"
    if time_series:
        shutil.copyfile(time_series, tmp_time_series_dir)

    # Define docker image
    image = "adriansegura99/geneci_optimize-ensemble"

    # In case it is not available on the device, it is downloaded from the repository.
    if not image in available_images:
        print("Downloading docker image ...")
        client.images.pull(repository=image)

    # The image is executed with the parameters set by the user.
    container = client.containers.run(
        image=image,
        volumes=get_volume("tmp"),
        command=f"tmp/ {crossover} {crossover_probability} {mutation} {mutation_probability} {repairer} {population_size} {num_evaluations} {cut_off_criteria} {cut_off_value} {functions} {algorithm} {threads} {plot_evolution}",
        detach=True,
        tty=True,
    )

    # Wait, stop and remove the container. Then print reported logs
    logs = wait_and_close_container(container)
    print(logs)

    # If specified, the evolution of the fitness values ​​is graphed
    if plot_evolution:

        # Open the file with the fitness values
        f = open("tmp/ea_consensus/fitness_evolution.txt", "r")

        # Each line contains the evolution of a different objective
        lines = f.readlines()

        # For each target ...
        for i in range(len(lines)):

            # Read the evolution of its values
            str_fitness = lines[i].split(", ")

            # Convert it to the appropriate type (float)
            fitness = [float(i) for i in str_fitness]

            # Plot it under the label of its function
            plt.plot(fitness, label=function[i])

        # Customize and save the figure
        plt.title("Fitness evolution")
        plt.ylabel("Fitness")
        plt.xlabel("Generation")
        plt.legend()
        plt.savefig("tmp/ea_consensus/fitness_evolution.pdf")
        plt.close()

    # If there are two objectives the pareto front is plotted
    if len(function) == 2:

        # Open the file with the fitness values associated with the non-dominated solutions.
        f = open("tmp/ea_consensus/FUN.csv", "r")

        # Each line contains the fitness values of a solution of the pareto front.
        lines = f.readlines()

        # The vectors that will store these values are created
        fitness_o1 = np.empty(0)
        fitness_o2 = np.empty(0)

        # For each solution add its value to the list
        for line in lines:
            point = line.split(",")
            fitness_o1 = np.append(fitness_o1, float(point[0]))
            fitness_o2 = np.append(fitness_o2, float(point[1]))

        # Obtain the order corresponding to the first objective in order to plot the front in an appropriate way.
        sorted_idx = np.argsort(fitness_o1)

        # Sort both vectors according to the indices obtained above.
        fitness_o1 = [fitness_o1[i] for i in sorted_idx]
        fitness_o2 = [fitness_o2[i] for i in sorted_idx]

        # Plot, customize, save the figure
        plt.plot(fitness_o1, fitness_o2, marker = '.')
        plt.title("Pareto front")
        plt.xlabel(function[0])
        plt.ylabel(function[1])
        plt.savefig("tmp/ea_consensus/pareto_front.pdf")
        plt.close()

    # Define and create the output folder
    if str(output_dir) == "<<conf_list_path>>/../ea_consensus":
        output_dir = Path(f"{Path(confidence_list[0]).parents[1]}/ea_consensus")
    output_dir.mkdir(exist_ok=True, parents=True)

    # All output files are moved and the temporary directory is deleted
    for f in Path("tmp/ea_consensus").glob("*"):
        shutil.move(f, f"{output_dir}/{f.name}")
    shutil.rmtree("tmp")


# Commands to evaluate the accuracy of DREAM inferred networks
## Command for evaluate one list
@dream_prediction_app.command()
def dream_list_of_links(
    challenge: Challenge = typer.Option(
        ..., help="DREAM challenge to which the inferred network belongs"
    ),
    network_id: str = typer.Option(..., help="Predicted network identifier. Ex: 10_1"),
    synapse_file: List[Path] = typer.Option(
        ...,
        help="Paths to files from synapse needed to perform inference evaluation. To download these files you need to register at https://www.synapse.org/# and download them manually or run the command extract-data evaluation-data.",
    ),
    confidence_list: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        help="Path to the CSV file with the list of trusted values.",
    ),
):
    """
    Evaluate one list of links with confidence levels.
    """

    # Report information to the user.
    print(
        f"Evaluate {confidence_list} prediction for {network_id} network in {challenge.name} challenge"
    )

    # Create temporary folder
    Path("tmp/synapse/").mkdir(exist_ok=True, parents=True)

    # Copy evaluation files
    tmp_synapse_files_dir = "tmp/synapse/"
    for f in synapse_file:
        shutil.copyfile(f, tmp_synapse_files_dir + Path(f).name)

    # Copy confidence list
    tmp_confidence_list_dir = f"tmp/{Path(confidence_list).name}"
    shutil.copyfile(confidence_list, tmp_confidence_list_dir)

    # Define docker image
    image = "adriansegura99/geneci_evaluate_dream-prediction"

    # In case it is not available on the device, it is downloaded from the repository.
    if not image in available_images:
        print("Downloading docker image ...")
        client.images.pull(repository=image)

    # The image is executed with the parameters set by the user.
    container = client.containers.run(
        image=image,
        volumes=get_volume("tmp"),
        command=f"--challenge {challenge.name} --network-id {network_id} --synapse-folder {tmp_synapse_files_dir} --confidence-list {tmp_confidence_list_dir}",
        detach=True,
        tty=True,
    )

    # Wait, stop and remove the container. Then print reported logs
    logs = wait_and_close_container(container)
    print(logs)

    # Delete temp folder
    shutil.rmtree("tmp")

    # For coding use
    return logs


## Command for evaluate weight distribution
@dream_prediction_app.command()
def dream_weight_distribution(
    challenge: Challenge = typer.Option(
        ..., help="DREAM challenge to which the inferred network belongs"
    ),
    network_id: str = typer.Option(..., help="Predicted network identifier. Ex: 10_1"),
    synapse_file: List[Path] = typer.Option(
        ...,
        help="Paths to files from synapse needed to perform inference evaluation. To download these files you need to register at https://www.synapse.org/# and download them manually or run the command extract-data evaluation-data.",
    ),
    weight_file_summand: Optional[List[str]] = typer.Option(
        ...,
        help="Paths of the CSV files with the confidence lists together with its associated weights. Example: 0.7*/path/to/list.csv",
    ),
):
    """
    Evaluate one weight distribution.
    """

    # Calculate the list of links from the distribution of weights
    weighted_confidence(
        weight_file_summand=weight_file_summand,
        output_file=Path("./tmp2/temporal_list.csv"),
    )

    # Calculate the AUROC and AUPR values for the generated list.
    values = dream_list_of_links(
        challenge=challenge,
        network_id=network_id,
        synapse_file=synapse_file,
        confidence_list="./tmp2/temporal_list.csv",
    )

    # Delete temp folder
    shutil.rmtree("tmp2")

    # For coding use
    return values


## Command for evaluate pareto front
@dream_prediction_app.command()
def dream_pareto_front(
    challenge: Challenge = typer.Option(
        ..., help="DREAM challenge to which the inferred network belongs"
    ),
    network_id: str = typer.Option(..., help="Predicted network identifier. Ex: 10_1"),
    synapse_file: List[Path] = typer.Option(
        ...,
        help="Paths to files from synapse needed to perform inference evaluation. To download these files you need to register at https://www.synapse.org/# and download them manually or run the command extract-data evaluation-data.",
    ),
    weights_file: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        help="File with the weights corresponding to a pareto front.",
    ),
    fitness_file: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        help="File with the fitness values corresponding to a pareto front.",
    ),
    confidence_list: Optional[List[str]] = typer.Option(
        ...,
        help="Paths to the CSV files with the confidence lists in the same order in which the weights and fitness values are specified in the corresponding files.",
    ),
    output_file: Path = typer.Option("./evaluated_front.csv", help="Output file path"),
    plot_front: bool = typer.Option(
        True,
        help="Indicate if you want to represent pareto front with AUROC and AUPR metrics.",
    ),
):
    """
    Evaluate pareto front.
    """

    # 1. Fitness Values
    ## Open the file with the fitness values associated with the non-dominated solutions.
    f = open(fitness_file, "r")

    ## Each line contains the fitness values of a solution of the pareto front.
    lines = f.readlines()

    ## The vectors that will store these values are created
    fitness_o1 = np.empty(0)
    fitness_o2 = np.empty(0)

    ## For each solution add its value to the list
    for line in lines:
        point = line.split(",")
        fitness_o1 = np.append(fitness_o1, float(point[0]))
        fitness_o2 = np.append(fitness_o2, float(point[1]))

    ## Obtain the order corresponding to the first objective in order to plot the front in an appropriate way.
    sorted_idx = np.argsort(fitness_o1)

    ## Sort both vectors according to the indices obtained above.
    fitness_o1 = [fitness_o1[i] for i in sorted_idx]
    fitness_o2 = [fitness_o2[i] for i in sorted_idx]

    # 2. Distribution of weights
    ## Open the file with the weights assigned to each inference technique.
    f = open(weights_file, "r")

    ## Each line contains the distribution of weights proposed by a solution of the pareto front.
    lines = f.readlines()

    ## The vector that will store the vectors with these weights is created (list formed by lists).
    weights = list()

    ## For each weight distribution ...
    for line in lines:

        # Converts to the appropriate type (float)
        solution = [float(w) for w in line.split(",")]

        # Added to the list
        weights.append(solution)

    ## Finally, it is ordered according to the previously obtained indexes to maintain concordance with the previous lists.
    weights = [weights[i] for i in sorted_idx]

    # 3. Evaluation Metrics
    ## The lists where the auroc and aupr values are going to be stored are created.
    auprs = list()
    aurocs = list()

    ## For each weight distribution (solution) ...
    for solution in weights:

        # The list of summands formed by products between the weights and the inference files provided in the input is constructed.
        weight_file_summand = list()
        for i in range(len(solution)):
            weight_file_summand.append(f"{solution[i]}*{confidence_list[i]}")

        # The function responsible for evaluating weight distributions is called
        values = dream_weight_distribution(
            challenge=challenge,
            network_id=network_id,
            synapse_file=synapse_file,
            weight_file_summand=weight_file_summand,
        )

        # The obtained accuracy values are read and stored in the list.
        str_aupr = re.search("AUPR: (.*)\n", values)
        auprs.append(float(str_aupr.group(1)))
        str_auroc = re.search("AUROC: (.*)\n", values)
        aurocs.append(float(str_auroc.group(1)))

    # 4. Writing the output CSV file
    ## The file path is created
    output_file.parent.mkdir(exist_ok=True, parents=True)

    ## The content of the obtained vectors is written
    with open(output_file, "w") as f:
        f.write(
            f"Weights{''.join([',' for i in range(len(confidence_list)-1)])},Fitness Values,,Evaluation Values,\n"
        )
        f.write(
            f"{','.join([Path(f).name for f in confidence_list])},Objective 1,Objective 2,AUROC,AUPR\n"
        )
        for i in range(len(sorted_idx)):
            f.write(
                f"{','.join([str(w) for w in weights[i]])},{fitness_o1[i]},{fitness_o2[i]},{aurocs[i]},{auprs[i]}\n"
            )
        f.close()

    # 5. Plot the information on a graph if specified
    if plot_front:
        plt.plot(fitness_o1, fitness_o2, marker = '.', label="Fitness Values")
        plt.plot(fitness_o1, aurocs, marker = '.', label="AUROC")
        plt.plot(fitness_o1, auprs, marker = '.', label="AUPR")
        plt.title("Pareto front")
        plt.xlabel("Objective 1")
        plt.ylabel("Objective 2")
        plt.legend()
        plt.savefig(f"{output_file.parent}/{output_file.stem}.pdf")
        plt.close()


# Command to evaluate the accuracy of generic inferred networks
@generic_prediction_app.command()
def generic_list_of_links(
    inferred_binary_matrix: Path = typer.Option(
        ..., exists=True, file_okay=True, help="Binary network to be evaluated"
    ),
    gs_binary_matrix: Path = typer.Option(
        ..., exists=True, file_okay=True, help="Gold standard binary network"
    ),
):
    """
    Evaluate one list of links with confidence levels.
    """
    # Report information to the user.
    print(
        f"Evaluate {inferred_binary_matrix} prediction with respect {gs_binary_matrix} gold standard"
    )

    # Create temporary folder
    Path("tmp/").mkdir(exist_ok=True)

    # Copy the network to test
    tmp_ibm_dir = f"tmp/{Path(inferred_binary_matrix).name}"
    shutil.copyfile(inferred_binary_matrix, tmp_ibm_dir)

    # And its respective gold standard
    tmp_gsbm_dir = f"tmp/{Path(gs_binary_matrix).name}"
    shutil.copyfile(gs_binary_matrix, tmp_gsbm_dir)

    # Define docker image
    image = "adriansegura99/geneci_evaluate_generic-prediction"

    # In case it is not available on the device, it is downloaded from the repository.
    if not image in available_images:
        print("Downloading docker image ...")
        client.images.pull(repository=image)

    # The image is executed with the parameters set by the user.
    container = client.containers.run(
        image=image,
        volumes=get_volume("tmp"),
        command=f"{tmp_ibm_dir} {tmp_gsbm_dir}",
        detach=True,
        tty=True,
    )

    # Wait, stop and remove the container. Then print reported logs
    logs = wait_and_close_container(container)
    print(logs)

    # Delete temp folder
    shutil.rmtree("tmp")


# Command that unites individual inference with consensus optimization
@app.command(rich_help_panel="Main Command")
def run(
    expression_data: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        help="Path to the CSV file with the expression data. Genes are distributed in rows and experimental conditions (time series) in columns.",
        rich_help_panel="Input data",
    ),
    technique: Optional[List[Technique]] = typer.Option(
        ...,
        case_sensitive=False,
        help="Inference techniques to be performed.",
        rich_help_panel="Individual inference",
    ),
    crossover: Crossover = typer.Option(
        "SBXCrossover", help="Crossover operator", rich_help_panel="Crossover"
    ),
    crossover_probability: float = typer.Option(
        0.9, help="Crossover probability", rich_help_panel="Crossover"
    ),
    mutation: Mutation = typer.Option(
        "PolynomialMutation", help="Mutation operator", rich_help_panel="Mutation"
    ),
    mutation_probability: float = typer.Option(
        -1,
        help="Mutation probability. [default: 1/len(files)]",
        show_default=False,
        rich_help_panel="Mutation",
    ),
    repairer: Repairer = typer.Option(
        "StandardizationRepairer",
        help="Solution repairer to keep the sum of weights equal to 1",
        rich_help_panel="Repairer",
    ),
    population_size: int = typer.Option(
        100, help="Population size", rich_help_panel="Diversity and depth"
    ),
    num_evaluations: int = typer.Option(
        25000, help="Number of evaluations", rich_help_panel="Diversity and depth"
    ),
    cut_off_criteria: CutOffCriteria = typer.Option(
        "MinConfDist",
        case_sensitive=False,
        help="Criteria for determining which links will be part of the final binary matrix.",
        rich_help_panel="Cut-Off",
    ),
    cut_off_value: float = typer.Option(
        0.5,
        help="Numeric value associated with the selected criterion. Ex: MinConfidence = 0.5, MaxNumLinksBestConf = 10, MinConfDist = 0.2",
        rich_help_panel="Cut-Off",
    ),
    function: Optional[List[str]] = typer.Option(
        ["Quality", "Topology"],
        help="A mathematical expression that defines a particular fitness function based on the weighted sum of several independent terms. Available terms: Quality, Topology and Loyalty.",
        rich_help_panel="Fitness",
    ),
    algorithm: Algorithm = typer.Option(
        "NSGAII",
        help="Evolutionary algorithm to be used during the optimization process. All are intended for a multi-objective approach with the exception of the genetic algorithm (GA).",
        rich_help_panel="Orchestration",
    ),
    threads: int = typer.Option(
        multiprocessing.cpu_count(),
        help="Number of threads to be used during parallelization. By default, the maximum number of threads available in the system is used.",
        rich_help_panel="Orchestration",
    ),
    plot_evolution: bool = typer.Option(
        False,
        help="Indicate if you want to represent the evolution of the fitness value.",
        rich_help_panel="Graphics",
    ),
    output_dir: Path = typer.Option(
        Path("./inferred_networks"),
        help="Path to the output folder.",
        rich_help_panel="Output",
    ),
):
    """
    Infer gene regulatory network from expression data by employing multiple unsupervised learning techniques and applying a genetic algorithm for consensus optimization.
    """

    # Report information to the user.
    print(f"\n Run algorithm for {expression_data}")

    # Run inference command
    infer_network(expression_data, technique, output_dir)

    # Extract results
    confidence_list = list(
        Path(f"./{output_dir}/{expression_data.stem}/lists/").glob("GRN_*.csv")
    )
    gene_names = Path(f"./{output_dir}/{expression_data.stem}/gene_names.txt")

    # Run ensemble optimization command
    optimize_ensemble(
        confidence_list,
        gene_names,
        crossover,
        crossover_probability,
        mutation,
        mutation_probability,
        repairer,
        population_size,
        num_evaluations,
        cut_off_criteria,
        cut_off_value,
        function,
        algorithm,
        threads,
        plot_evolution,
        output_dir="<<conf_list_path>>/../ea_consensus",
    )


# Command for graphical representation of networks.
@app.command(rich_help_panel="Additional commands")
def draw_network(
    confidence_list: Optional[List[str]] = typer.Option(
        ..., help="Paths of the CSV files with the confidence lists to be represented"
    ),
    mode: Mode = typer.Option("Both", help="Mode of representation"),
    nodes_distribution: NodesDistribution = typer.Option(
        "Spring", help="Node distribution in graph"
    ),
    output_folder: Path = typer.Option(
        "<<conf_list_path>>/../network_graphics", help="Path to output folder"
    ),
):
    """
    Draw gene regulatory networks from confidence lists.
    """

    # Report information to the user.
    print(f"\n Draw gene regulatory networks for {', '.join(confidence_list)}")

    # Create input temporary folder.
    tmp_input_folder = "tmp/input"
    Path(tmp_input_folder).mkdir(exist_ok=True, parents=True)

    # Create output temporary folder.
    tmp_output_folder = "tmp/output"
    Path(tmp_output_folder).mkdir(exist_ok=True, parents=True)

    # Create input command and copy the trust lists to represent.
    command = ""
    for file in confidence_list:
        tmp_file_dir = f"{tmp_input_folder}/{Path(file).name}"
        command += f"--confidence-list {tmp_file_dir} "
        shutil.copyfile(file, tmp_file_dir)

    # Define docker image
    image = "adriansegura99/geneci_draw-network"

    # In case it is not available on the device, it is downloaded from the repository.
    if not image in available_images:
        print("Downloading docker image ...")
        client.images.pull(repository=image)

    # The image is executed with the parameters set by the user.
    container = client.containers.run(
        image=image,
        volumes=get_volume("tmp"),
        command=f"{command} --mode {mode} --nodes-distribution {nodes_distribution} --output-folder {tmp_output_folder}",
        detach=True,
        tty=True,
    )

    # Wait, stop and remove the container. Then print reported logs
    logs = wait_and_close_container(container)
    print(logs)

    # Define and create the output folder
    if str(output_folder) == "<<conf_list_path>>/../network_graphics":
        output_folder = Path(f"{Path(confidence_list[0]).parents[1]}/network_graphics/")
    output_folder.mkdir(exist_ok=True, parents=True)

    # Move all output files
    for f in Path(tmp_output_folder).glob("*"):
        shutil.move(f, f"{output_folder}/{f.name}")

    # Delete temporary directory
    shutil.rmtree("tmp")


# Command for get weighted confidence levels from files and a given distribution of weights
@app.command(rich_help_panel="Additional commands")
def weighted_confidence(
    weight_file_summand: Optional[List[str]] = typer.Option(
        ...,
        help="Paths of the CSV files with the confidence lists together with its associated weights. Example: 0.7*/path/to/list.csv",
    ),
    output_file: Path = typer.Option(
        "<<conf_list_path>>/../weighted_confidence.csv", help="Output file path"
    ),
):
    """
    Calculate the weighted sum of the confidence levels reported in various files based on a given distribution of weights.
    """

    # Report information to the user.
    print(
        f"\n Calculating the weighted sum of confidence levels for entry {', '.join(weight_file_summand)}"
    )

    # Create input temporary folder.
    tmp_input_folder = "tmp/input"
    Path(tmp_input_folder).mkdir(exist_ok=True, parents=True)

    # Create output temporary folder.
    tmp_output_folder = "tmp/output"
    Path(tmp_output_folder).mkdir(exist_ok=True, parents=True)

    # Define default temporary output file
    tmp_output_file = f"{tmp_output_folder}/{output_file.name}"

    # The entered summands are validated.
    ## Instantiate a variable to store the cumulative sum of weights
    sum = 0

    ## Instantiate another variable to store the new command with the temporary paths of the input files
    command = ""

    ## For each summand ...
    for summand in weight_file_summand:

        # Separate both products (weight and file)
        pair = summand.split("*")

        # If two elements are not detected, an error is thrown.
        if len(pair) != 2:
            print(
                f"[bold red]Error:[/bold red] The entry {summand} is invalid, remember to separate weight and file name by the '*' character"
            )
            raise typer.Abort()

        # Extract the weight
        weight = pair[0]

        # Convert it to the appropriate rate and add it to the accumulated sum.
        sum += float(weight)

        # Extract the file
        file = pair[1]

        # Define temporary file path and copy to it
        tmp_file_dir = f"{tmp_input_folder}/{Path(file).name}"
        shutil.copyfile(file, tmp_file_dir)

        # Add to command
        command += f" {weight}*{tmp_file_dir}"

    # If the sum of weights is not 1, an exception is thrown.
    if abs(sum - 1) > 0.01:
        print("[bold red]Error:[/bold red] The sum of the weights must be 1")
        raise typer.Abort()

    # Define docker image
    image = "adriansegura99/geneci_weighted-confidence"

    # In case it is not available on the device, it is downloaded from the repository.
    if not image in available_images:
        print("Downloading docker image ...")
        client.images.pull(repository=image)

    # The image is executed with the parameters set by the user.
    container = client.containers.run(
        image=image,
        volumes=get_volume("tmp"),
        command=f"{tmp_output_file} {command}",
        detach=True,
        tty=True,
    )

    # Wait, stop and remove the container. Then print reported logs
    logs = wait_and_close_container(container)
    print(logs)

    # Define and create the output folder
    if str(output_file) == "<<conf_list_path>>/../weighted_confidence.csv":
        output_file = Path(f"{Path(file).parents[1]}/weighted_confidence.csv")
    output_file.parent.mkdir(exist_ok=True, parents=True)

    # Output file is moved and the temporary directory is deleted
    shutil.move(tmp_output_file, output_file)
    shutil.rmtree("tmp")


if __name__ == "__main__":
    app()
