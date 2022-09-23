package eagrn;

import eagrn.cutoffcriteria.CutOffCriteria;
import eagrn.fitnessfunctions.FitnessFunction;
import eagrn.fitnessfunctions.impl.Loyalty;
import eagrn.fitnessfunctions.impl.Quality;
import eagrn.fitnessfunctions.impl.Topology;
import eagrn.operator.repairer.WeightRepairer;
import java.io.File;
import java.util.*;

import org.uma.jmetal.problem.doubleproblem.impl.AbstractDoubleProblem;
import org.uma.jmetal.solution.doublesolution.DoubleSolution;
import org.uma.jmetal.solution.doublesolution.impl.DefaultDoubleSolution;


public class GRNProblem extends AbstractDoubleProblem {
    private Map<String, Double[]> inferredNetworks;
    private Map<String, MedianTuple> medianInterval;
    private ArrayList<String> geneNames;
    private WeightRepairer initialPopulationRepairer;
    private CutOffCriteria cutOffCriteria;
    protected FitnessFunction[] fitnessFunctions;
    private String strTimeSeriesFile;

    /** Constructor creates a default instance of the GRN problem */
    public GRNProblem(File[] inferredNetworkFiles, ArrayList<String> geneNames, WeightRepairer initialPopulationRepairer, CutOffCriteria cutOffCriteria, String strFitnessFormulas, String strTimeSeriesFile) {
        
        this.inferredNetworks = StaticUtils.readAll(inferredNetworkFiles);
        this.medianInterval = StaticUtils.calculateMedian(inferredNetworks);
        this.geneNames = geneNames;
        this.initialPopulationRepairer = initialPopulationRepairer;
        this.cutOffCriteria = cutOffCriteria;
        this.strTimeSeriesFile = strTimeSeriesFile;

        /** Parse fitness functions */
        String[] formulas = strFitnessFormulas.split(";");
        this.fitnessFunctions = new FitnessFunction[formulas.length];

        for (int i = 0; i < formulas.length; i++) {
            String[] subformulas = formulas[i].split("\\+");
            FitnessFunction function;
            if (subformulas.length == 1) {
                String[] tuple = subformulas[0].split("\\*");
                switch (tuple.length) {
                    case 1:
                        function = getFitnessFunction(tuple[0]);
                        break;
                    case 2:
                        double weight;
                        try {
                            weight = Double.parseDouble(tuple[0]);
                        } catch (Exception e) {
                            throw new RuntimeException("The weight " + tuple[0] + " assigned to term " + tuple[1] + " is invalid.");
                        }
                        if (weight != 1) {
                            throw new RuntimeException("If the fitness function consists of a single term, its weight must be 1. However, " + tuple[0] + " has been provided.");
                        }
                        function = getFitnessFunction(tuple[1]);
                        break;
                    default:
                        throw new RuntimeException("Function specified with improper formatting. Remember to separate the name of the terms by the symbol +, and assign their weight by preceding them with a decimal followed by the symbol *.");
                }
                
            } else {
                FitnessFunction[] functions = new FitnessFunction[subformulas.length];
                Double[] weights = new Double[subformulas.length];
                double totalWeight = 0;

                for (int j = 0; j < subformulas.length; j++) {
                    String[] tuple = subformulas[j].split("\\*");
                    if (tuple.length != 2) {
                        throw new RuntimeException("Function specified with improper formatting. Remember to separate the name of the terms by the symbol +, and assign their weight by preceding them with a decimal followed by the symbol *.");
                    }

                    functions[j] = getFitnessFunction(tuple[1]);
                    try {
                        weights[j] = Double.parseDouble(tuple[0]);
                        totalWeight += weights[j];
                    } catch (Exception e) {
                        throw new RuntimeException("The weight " + tuple[0] + " assigned to term " + tuple[1] + " is invalid.");
                    }
                }

                if (totalWeight != 1) {
                    throw new RuntimeException("The weights of all the terms in the formula must add up to 1.");
                }

                function = (Map<String, ConsensusTuple> consensus) -> {
                    double res = 0;
                    for (int j = 0; j < functions.length; j++) {
                        res += weights[j] * functions[j].run(consensus);
                    }
                    return res;
                };
            }
            this.fitnessFunctions[i] = function;
        }

        setNumberOfVariables(inferredNetworkFiles.length);
        setNumberOfObjectives(this.fitnessFunctions.length);
        setName("GRNProblem");

        List<Double> lowerLimit = new ArrayList<>(getNumberOfVariables());
        List<Double> upperLimit = new ArrayList<>(getNumberOfVariables());

        for (int i = 0; i < getNumberOfVariables(); i++) {
            lowerLimit.add(0.0);
            upperLimit.add(1.0);
        }

        setVariableBounds(lowerLimit, upperLimit);
    }

    /** CreateSolution() method */
    @Override
    public DoubleSolution createSolution() {
        DefaultDoubleSolution solution = new DefaultDoubleSolution(this.getNumberOfObjectives(), this.getNumberOfConstraints(), this.getBoundsForVariables());
        initialPopulationRepairer.repairSolution(solution);
        return solution;
    }

    /** Evaluate() method */
    @Override
    public DoubleSolution evaluate(DoubleSolution solution) {
        double[] x = new double[getNumberOfVariables()];
        for (int i = 0; i < getNumberOfVariables(); i++) {
            x[i] = solution.variables().get(i);
        }

        Map<String, ConsensusTuple> consensus = makeConsensus(x);
        for (int i = 0; i < fitnessFunctions.length; i++){
            solution.objectives()[i] = fitnessFunctions[i].run(consensus);
        }

        return solution;
    }

    /** GetFitnessFunction() method */
    private FitnessFunction getFitnessFunction(String str) {
        /** 
         * Function to return FitnessFunction object based on a string 
         */
        
        FitnessFunction res;
        switch (str.toLowerCase()) {
            case "topology":
                res = new Topology(this.geneNames, this.cutOffCriteria);
                break;
            case "quality":
                res = new Quality(this.geneNames.size());
                break;
            case "loyalty":
                res = new Loyalty(this.strTimeSeriesFile);
                break;
            default:
                throw new RuntimeException("The evaluation term " + str + " is not implemented.");
        }
        return res;
    }

    /** MakeConsensus() method */
    public Map<String, ConsensusTuple> makeConsensus(double[] x) {
        /**
         * Elaborate the list of consensus links from the vector of weights
         * and the results provided by each technique.
         */

        Map<String, ConsensusTuple> consensus = new HashMap<>();

        for (Map.Entry<String, Double[]> pair : inferredNetworks.entrySet()) {
            ConsensusTuple mapConsTuple = new ConsensusTuple(0.0, 0.0);
            MedianTuple medInt = medianInterval.get(pair.getKey());
            Double[] weightDistances = new Double[x.length];

            for (int i = 0; i < x.length; i++) {
                mapConsTuple.increaseConf(x[i] * pair.getValue()[i]);
                weightDistances[i] = ((Math.abs(medInt.getMedian() - pair.getValue()[i]) / medInt.getInterval()) + x[i]) / 2.0;
            }

            double min = Collections.min(Arrays.asList(weightDistances));
            double max = Collections.max(Arrays.asList(weightDistances));

            mapConsTuple.setDist(max - min);
            consensus.put(pair.getKey(), mapConsTuple);
        }

        return consensus;
    }

    @Override
    public void setName(String name) {
        super.setName(name);
    }
 
}
