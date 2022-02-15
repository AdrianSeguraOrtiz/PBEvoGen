package operator.mutationwithrepair.impl;

import operator.repairer.WeightRepairer;
import org.uma.jmetal.operator.mutation.impl.NullMutation;
import org.uma.jmetal.solution.doublesolution.DoubleSolution;
import org.uma.jmetal.util.errorchecking.JMetalException;

public class NullMutationWithRepair extends NullMutation<DoubleSolution> {
    private WeightRepairer repairer;

    public NullMutationWithRepair(WeightRepairer repairer) {
        this.repairer = repairer;
    }

    @Override
    public DoubleSolution execute(DoubleSolution solution) throws JMetalException {
        repairer.repairSolution(solution);
        return solution;
    }
}
